from abc import ABC, abstractmethod
import json
import os
from dataclasses import dataclass
from aalchem.vllm.transition_model.template.reaction_transition_template import BasePopulatedTemplate
from aalchem.vllm.transition_model.template.reaction_transition_template import ReactionTransitionPopulator


@dataclass
class Choice:
    index: int
    message: dict


@dataclass
class OpenAIResponse:
    """
    Response akin to the OpenAI API. In order to unify the response from the different models, we use this class.
    """
    id: str
    created: int
    model: str
    choices: list[Choice]
    usage: dict

    def __post_init__(self):
        self.choices = [Choice(**choice) for choice in self.choices]


def template_from_smiles(smiles: str, prompt_template_path: str) -> None:
    """
    Populate the template with the data.
    """
    populator = ReactionTransitionPopulator(prompt_template_path)
    template = populator.populate_templates([smiles])
    return template


class BaseModel(ABC):
    """
    Base class for all models.
    """

    @abstractmethod
    def get_response(
            self,
            query: str,
            thinking: bool = False,
            **kwargs
        ) -> str:
        """
        Get the response from the model.
        Args:
            query: str -> the query to the model

        Returns:
            str -> the response from the model
        """
        pass

    @abstractmethod
    def postprocess(self, response):
        """
        Postprocess the response.
        """
        pass

    def predict_template(
            self,
            template: BasePopulatedTemplate,
            thinking: bool = True,
            thinking_budget_tokens: int = 10000,
            write_to_file: bool = False,
            output_dir: str = None,
            **kwargs
        ) -> str:
        """
        Predict the template.
        """

        ## Get response in OpenAI format
        response = self.get_response(
            query=template.prompt,
            thinking=thinking,
            thinking_budget_tokens=thinking_budget_tokens
        )

        response_json = self.postprocess(response)

        template_data = {}
        for field_name in template.__dataclass_fields__:
            template_data[field_name] = getattr(template, field_name)

        output_data = {
            "template_data": template_data,
            "response": response_json
        }

        if write_to_file:
            with open(os.path.join(output_dir, f"response_{template.id}.json"), "w") as f:
                json.dump(output_data, f)
        return output_data