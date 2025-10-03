
def build_open_ai_response(
        id: str, 
        model: str, 
        content: str,
        reasoning_content: str,
        prompt_tokens: int,
        completion_tokens: int,
        created: int = None, 
    ) -> dict:
    """
    Build a response similar to the OpenAI response.
    """
    return {
        "id": id,
        'object': 'chat.completion',
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "reasoning_content": reasoning_content,
                    'tool_calls': []

                },
                "logprobs": None,
                "finish_reason": "length",
                "stop_reason": None
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            'prompt_tokens_details': None
        },
        'prompt_logprobs': None,
        'kv_transfer_params': None,
    }
