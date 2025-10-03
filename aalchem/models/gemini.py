import os
import vertexai
import datetime
from pprint import pprint 
from aalchem.config import ModelConfig
from aalchem.config import paths
from google import genai
from google.genai import types
from vertexai.generative_models import GenerativeModel
from vertexai.tuning import sft
from aalchem.models.base import BaseModel
from aalchem.models.responses import build_open_ai_response


def gemini_to_openai_format(response) -> dict:
    """
    Convert the response to the OpenAI format.
    """
    parts = response.candidates[0].content.parts

    if len(parts) > 1:
        generated_text = ""
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'thought') and part.thought:
                thinking = part.text
            else:
                generated_text += part.text
        output = generated_text
    else:
        thinking = ""
        output = parts[0].text

    total_tokens = response.usage_metadata.total_token_count
    thinking_tokens = response.usage_metadata.thoughts_token_count
    completion_tokens = total_tokens - thinking_tokens
    return build_open_ai_response(
        id=response.response_id,
        model=response.model_version,
        content=output,
        reasoning_content=thinking,
        prompt_tokens=thinking_tokens,
        completion_tokens=completion_tokens,
        created=None
    )


def load_config(model_name: str, **kwargs) -> ModelConfig:
    """
    Loads the finetuned model config from the config.yaml file in the models directory.

    Args:
        name: str -> name of the model

    Returns:
        ModelConfig -> model config
    """
    path = paths.MODELS / model_name / 'config.yaml'
    if not os.path.exists(path):
        print(f"Config file for {model_name} does not exist. Using default retro_llm.config.ModelConfig.")
        config = ModelConfig()
    else:
        print(f"Loading config from {path}")
        config = ModelConfig().from_yaml(path)

    for var, value in kwargs.items():
        if value is not None:
            setattr(config, var, value)

    return config


class GeminiVertexModel(BaseModel):
    """
    Class for fine-tuned  or default Gemini models.
    """
    def __init__(
            self, 
            name: str = 'gemini-2.5-flash', 
            location: str = None, 
            project: str = None, 
            checkpoint: int = None
        ) -> None:

        self.name = name
        self.endpoint = None
        self.config = load_config(
            model_name=name, 
            location=location, 
            project=project, 
            checkpoint=checkpoint
        )
        self.client = genai.Client(
            project=self.config.project,
            location=self.config.location,
            vertexai=True
        )
        if self.config.checkpoint is not None:
            self.name = self.name+f'_{self.config.checkpoint}'

        if self.config.endpoint is None and name not in self.available_models():
            self.endpoint = self.get_endpoint(display_name=name)
        else:
            self.endpoint = self.config.endpoint
        self.summary()
                
    def get_response(
            self, 
            query: str, 
            thinking: bool = False, 
            thinking_budget_tokens: int = 10000,
            temperature: float = None
        ) -> str:
        """
        Call the model with a specific prompt
        """
        if self.config.system_prompt and self.config.use_prompt:
            query = self.config.system_prompt.format(text=query)

        self.generation_config = self.get_generation_config(
            thinking=thinking, 
            temperature=temperature,
            thinking_budget_tokens=thinking_budget_tokens
        )
        
        return self.client.models.generate_content(
                model=self.endpoint if self.endpoint is not None else self.name,
                contents=query,
                config=self.generation_config,
            )
    
    def postprocess(self, response):
        return gemini_to_openai_format(response)

    def summary(self):
        """
        Print simple summary.
        """
        print(f'Model: {self.name}, endpoint: {self.endpoint}')
        print(f'Location: {self.config.location} | project: {self.config.project}')
        pprint(self.config)
        pprint(self.get_generation_config())

    def get_generation_config(
            self,
            thinking: bool = False, 
            temperature: float = None,
            thinking_budget_tokens: int = 10000
        ) -> types.GenerateContentConfig:
        """
        Get appropriate generation config.
        """
        self.generation_config = types.GenerateContentConfig(
            top_k=self.config.top_k,
            top_p=self.config.top_p,
            temperature=temperature if temperature is not None else 0 if self.config.inference else self.config.temperature,
            seed = 0,
            max_output_tokens = self.config.max_output_tokens,
        )
        if thinking:
            self.generation_config.thinking_config = types.ThinkingConfig(
                thinking_budget=thinking_budget_tokens,
                include_thoughts=True,
            )
        return self.generation_config

    def get_endpoint(self, display_name: str) -> str:
        """
        Given a model's display name, retrieve the one that is used in the API
        """
        for model in self.client.tunings.list():
            if model.tuned_model_display_name == display_name:
                if self.config.checkpoint is None:
                    return model.tuned_model.endpoint
                else:
                    return self.get_checkpoint(
                        checkpoint=self.config.checkpoint, 
                        model=model
                    ).endpoint
        return None
    
    def get_checkpoint(self, checkpoint: int, model: types.TuningJob) -> types.TunedModelCheckpoint:
        """
        Retrieves the particular checkpoint for a model
        """
        for checkpoint in model.tuned_model.checkpoints:
            if int(checkpoint.checkpoint_id) == self.config.checkpoint:
                return checkpoint

    def available_models(self) -> list[str]:
        """
        Returns a sorted list of base model names available on the platform.
        """
        return sorted([model.name.split('/')[-1] for model in self.client.models.list()])

    def tuned_models(self) -> list[GenerativeModel]:
        """
        Returns a list of all the stock models available on Vertex platform.
        """
        tuned = [model for model in self.client.tunings.list()]
        pprint(sorted([model.tuned_model_display_name for model in tuned]))
        return tuned
    
    def stock_models(self) -> list[GenerativeModel]:
        """
        Returns all available tuned model objects.
        """
        return [model for model in self.client.models.list()]
    
    def finetune(
            self, 
            run_name: str,
            train_dataset: str, 
            validation_dataset: str,
            epochs: int,
        ) -> None:
        """
        Finetunes on a particular dataset
        """

        date = datetime.datetime.now().strftime('%Y%m%d_%H%M')
        run_w_date = f'{run_name}_{date}'
        cloud_client = CloudDataset(project=self.config.project, location=self.config.location)
        if not isinstance(train_dataset, str):
            train_dataset = cloud_client.upload_dataset(
                dataset=train_dataset,
                system_prompt=self.config.system_prompt,
                bucket_name=run_w_date,
                blob_name=run_w_date
            )
        if not isinstance(validation_dataset, str):
            validation_dataset = cloud_client.upload_dataset(
                dataset=validation_dataset,
                system_prompt=self.config.system_prompt,
                bucket_name=run_w_date,
                blob_name=run_w_date
            )
        
        vertexai.init(
            project=self.config.project,
            location=self.config.location,
            api_key=os.environ.get('GOOGLE_API_KEY', None)
        )

        print(f'Finetuning model {self.name} on \n Training: {train_dataset} \n Validation: {validation_dataset}')
        name = self.name if self.endpoint is None else self.endpoint
        sft_tuning_job = sft.train(
            source_model=name,
            train_dataset=train_dataset,
            validation_dataset=validation_dataset,
            epochs=5,
            tuned_model_display_name=run_name
        )
