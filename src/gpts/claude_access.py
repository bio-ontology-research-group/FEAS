import os
import json
import anthropic
import google.generativeai as genai
import typing
import sys
root_dir = f"{__file__.split('src')[0]}"
if root_dir not in sys.path:
    sys.path.append(root_dir)

class ClaudeAccess(object):
    claude_model_info = {
        "claude-3-5-sonnet@20240620": {
            "token_limit_per_min": 4 * 10**4,  # Placeholder - need to find actual Gemini limits
            "request_limit_per_min": 50,  # Placeholder
            "max_token_per_prompt": 200000  # Up to 32k tokens for Gemini Pro
        },
        # Add more Gemini models here as needed
    }
    def __init__(self, api_key_file: str = ".secrets/claude_key.json", model_name: str = "claude-pro"):
        with open(".secrets/google_key.json", "r") as f:
            gem_api_key = json.load(f)["api_key"]
        genai.configure(api_key=gem_api_key)
        with open(api_key_file, "r") as f:
            api_key = json.load(f)["api_key"]
        self.client = anthropic.AnthropicVertex(region="us-east5", project_id=api_key)
        self.models_supported = list(self.claude_model_info.keys())
        assert model_name in self.models_supported, f"Model name {model_name} not supported"
        self.model_name = model_name
        self.is_open_ai_model = False
        self.usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }

    def complete_chat(self,
                      messages: typing.List[str],
                      model: typing.Optional[str] = None,
                      n: int = 1,
                      max_tokens: int = 5,
                      temperature: float = 0.25,
                      top_p: float = 1.0,
                      frequency_penalty: float = 0.0,
                      presence_penalty: float = 0.0,
                      stop: list = ["\n"]) -> typing.Tuple[list, dict]:
        model_name = model if model is not None else self.model_name
        content = ""
        for message in messages:
            content += "\n" + message["content"]
        messages = [{"role": "user", "content": content}]
        response = self.client.messages.create(
            model=model_name,
            max_tokens=max_tokens,
            messages=messages,
            stop_sequences=stop,
            temperature=temperature,
            top_p=top_p,

        )
        # Process response
        return_responses = [{"role": "assistant", "content": message.text}
                            for message in response.content]

        # Update usage
        usage_metadata = response.usage
        self.usage["prompt_tokens"] += usage_metadata.input_tokens
        self.usage["completion_tokens"] += usage_metadata.output_tokens
        self.usage["total_tokens"] += usage_metadata.input_tokens + usage_metadata.output_tokens
        for i in range(len(return_responses) - 1):
            return_responses[i]["finish_reason"] = "stop"
        return_responses[0]["finish_reason"] = "stop"
        usage_dict = {
            "prompt_tokens": usage_metadata.input_tokens,
            "completion_tokens": usage_metadata.output_tokens,
            "total_tokens": usage_metadata.input_tokens + usage_metadata.output_tokens,
            "reason": "stop"
        }
        return return_responses, usage_dict

    def num_tokens_from_messages(self, messages, model=None):

        gen_model = genai.GenerativeModel(model_name="gemini-1.5-pro")

        prompt = ""
        for message in messages:
            prompt += f"{message['role']}: {message['content']}\n"  # Format as a continuous prompt

        response = gen_model.count_tokens(prompt)
        return response.total_tokens
# class ClaudeAccess(object):
#     claude_model_info = {
#         "claude-3-5-sonnet-20240620": {
#             "token_limit_per_min": 4 * 10**4,  # Placeholder - need to find actual Gemini limits
#             "request_limit_per_min": 50,  # Placeholder
#             "max_token_per_prompt": 200000  # Up to 32k tokens for Gemini Pro
#         },
#         # Add more Gemini models here as needed
#     }
#     def __init__(self, api_key_file: str = ".secrets/claude_key.json", model_name: str = "claude-pro"):
#         with open(".secrets/gemini_key.json", "r") as f:
#             gem_api_key = json.load(f)["api_key"]
#         genai.configure(api_key=gem_api_key)
#         with open(api_key_file, "r") as f:
#             api_key = json.load(f)["api_key"]
#         self.client = anthropic.Anthropic(
#             api_key=api_key,
#         )
#         self.models_supported = list(self.claude_model_info.keys())
#         assert model_name in self.models_supported, f"Model name {model_name} not supported"
#         self.model_name = model_name
#         self.is_open_ai_model = False
#         self.usage = {
#             "prompt_tokens": 0,
#             "completion_tokens": 0,
#             "total_tokens": 0
#         }
#
#     def complete_chat(self,
#                       messages: typing.List[str],
#                       model: typing.Optional[str] = None,
#                       n: int = 1,
#                       max_tokens: int = 5,
#                       temperature: float = 0.25,
#                       top_p: float = 1.0,
#                       frequency_penalty: float = 0.0,
#                       presence_penalty: float = 0.0,
#                       stop: list = ["\n"]) -> typing.Tuple[list, dict]:
#         model_name = model if model is not None else self.model_name
#         content = ""
#         for message in messages:
#             content += "\n" + message["content"]
#         messages = [{"role": "user", "content": content}]
#         response = self.client.messages.create(
#             model=model_name,
#             max_tokens=max_tokens,
#             messages=messages,
#             stop_sequences=stop,
#             temperature=temperature,
#             top_p=top_p,
#
#         )
#         # Process response
#         return_responses = [{"role": "assistant", "content": message.text}
#                             for message in response.content]
#
#         # Update usage
#         usage_metadata = response.usage
#         self.usage["prompt_tokens"] += usage_metadata.input_tokens
#         self.usage["completion_tokens"] += usage_metadata.output_tokens
#         self.usage["total_tokens"] += usage_metadata.input_tokens + usage_metadata.output_tokens
#         for i in range(len(return_responses) - 1):
#             return_responses[i]["finish_reason"] = "stop"
#         return_responses[0]["finish_reason"] = "stop"
#         usage_dict = {
#             "prompt_tokens": usage_metadata.input_tokens,
#             "completion_tokens": usage_metadata.output_tokens,
#             "total_tokens": usage_metadata.input_tokens + usage_metadata.output_tokens,
#             "reason": "stop"
#         }
#         return return_responses, usage_dict
#
#     def num_tokens_from_messages(self, messages, model=None):
#
#         gen_model = genai.GenerativeModel(model_name="gemini-1.5-pro")
#
#         prompt = ""
#         for message in messages:
#             prompt += f"{message['role']}: {message['content']}\n"  # Format as a continuous prompt
#
#         response = gen_model.count_tokens(prompt)
#         return response.total_tokens
if __name__ == '__main__':
    print(root_dir)
    with open(root_dir+"/.secrets/claude_key2.json", "r") as f:
        api_key = json.load(f)["api_key"]
    client = anthropic.AnthropicVertex(region="us-east5 (Ohio)", project_id=api_key)
    message = client.messages.create(
        model="claude-3-5-sonnet@20240620",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": "Send me a recipe for banana bread.",
            }
        ],
    )
    print(message.model_dump_json(indent=2))