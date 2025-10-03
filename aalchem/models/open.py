## Placeholder for OpenAI 
import openai
import os
from aalchem.models.base import BaseModel

class OpenAIModel(BaseModel):
    """
    OpenAI model wrapper
    """
    def __init__(
            self, 
            name: str='gpt-5', 
            reasoning: str = "high",  # 'low', 'medium', 'high'
            verbosity: str = "high"  # 'low', 'medium', 'high'
        ) -> None:
        self.name = name
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.reasoning_level = reasoning  # 'low', 'medium', 'high'
        self.verbosity_level = verbosity  # 'low', 'medium', 'high'

    def predict(self, prompt: str) -> str:
        result = self.client.responses.create(
            model=self.name,
            input=prompt,
            reasoning={ "effort": "high"},
            text={ "verbosity": "low" },
        )
        return result.output_text

    def get_response(
            self, 
            query: str, 
            thinking: bool = True,
            temperature: float = 1.0, 
            thinking_budget_tokens: int = 512
        ) -> str:

        return self.client.responses.create(
            model=self.name,
            temperature=temperature,
            input=query,
            reasoning={ "effort": self.reasoning_level},
            text={ "verbosity": self.verbosity_level },
        )
        
    def postprocess(self, response):
        """
        Postprocess the response.
        """
        return response.dict()