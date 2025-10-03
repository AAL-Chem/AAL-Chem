import anthropic
import os
from aalchem.models.base import BaseModel
from aalchem.models.responses import build_open_ai_response


class AnthropicModel(BaseModel):
    def __init__(self, name: str = "claude-sonnet-4-20250514"):
        self.name = name
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.limits = {"claude-sonnet-4-20250514": 21000, "claude-3-haiku-20240307": 4096}

    def generate(
            self, 
            prompt: str, 
            max_tokens: int = 21000, 
            temperature: float = 1.0, 
            thinking: bool = False,
            thinking_budget_tokens: int = 30000
        ) -> str:

        if thinking:
            gen_kwargs = {
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": thinking_budget_tokens
                },
            }
            temperature = 2
        else:
            gen_kwargs = {}
        max_tokens = self.limits[self.name] if self.name in self.limits else max_tokens

        return self.client.messages.create(
            model=self.name,
            max_tokens=max_tokens,
            # temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
            **gen_kwargs,
        )

    def get_response(
            self, 
            query: str, 
            thinking: bool = False, 
            thinking_budget_tokens: int = 10000
        ) -> str:
        return self.generate(
            prompt=query, 
            thinking=thinking, 
            thinking_budget_tokens=thinking_budget_tokens
        )

    def postprocess(self, response):
        
        if len(response.content) < 2:
            thinking_content = ""
            text_content = response.content[0].text
        else:
            thinking_content = response.content[0].thinking
            text_content = response.content[1].text

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        full_response = build_open_ai_response(
            id=response.id,
            model=response.model,
            content=text_content,
            reasoning_content=thinking_content,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            created=None
        )
        return full_response