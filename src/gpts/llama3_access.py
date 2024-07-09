import os
import json
import replicate
import google.generativeai as genai
import typing
import sys
root_dir = f"{__file__.split('src')[0]}"
if root_dir not in sys.path:
    sys.path.append(root_dir)
class Llama3Access(object):
    llama_model_info = {
        "meta/meta-llama-3-70b-instruct": {
            "token_limit_per_min": 4 * 10**4,  # Placeholder - need to find actual Gemini limits
            "request_limit_per_min": 600,  # Placeholder
            "max_token_per_prompt": 8000  # Up to 32k tokens for Gemini Pro
        },
        # Add more Gemini models here as needed
    }
    def __init__(self, api_key_file: str = ".secrets/llama_key.json", model_name: str = "llama3"):
        with open(".secrets/gemini_key.json", "r") as f:
            gem_api_key = json.load(f)["api_key"]
        genai.configure(api_key=gem_api_key)
        with open(api_key_file, "r") as f:
            api_key = json.load(f)["api_key"]
        self.client = replicate.client.Client(
            api_token=api_key,
        )
        self.models_supported = list(self.llama_model_info.keys())
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
        for message in messages:
            if message["role"] == "system":
                system_prompt = message["content"]
            else:
                prompt = message["content"]
        inputs = {
            "top_p": top_p,
            "prompt": prompt,
            "system_prompt": system_prompt,
            "min_tokens": 0,
            "temperature": temperature,
            "presence_penalty": presence_penalty,
            "max_tokens": max_tokens
        }
        response = self.client.run("meta/meta-llama-3-70b-instruct", input=inputs)
        # Process response
        return_responses = [{"role": "assistant", "content": "".join(response)}]

        # Update usage
        self.usage["prompt_tokens"] += 0
        self.usage["completion_tokens"] += 0
        self.usage["total_tokens"] += 0
        for i in range(len(return_responses) - 1):
            return_responses[i]["finish_reason"] = "stop"
        return_responses[0]["finish_reason"] = "stop"
        usage_dict = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
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

if __name__ == "__main__":
    os.chdir(root_dir)

    # openai_access = GptAccess(model_name="gpt-3.5-turbo")
    openai_access = GeminiAccess(model_name="gemini-1.5-pro")
    # openai_access = GptAccess(model_name="davinci")
    # print(openai_access.get_models())
    messages = [
        {
            "role": "system",
            "content": "You are a helpful, pattern-following assistant that translates corporate jargon into plain English.",
        },
        {
            "role": "system",
            "name": "example_user",
            "content": "New synergies will help drive top-line growth.",
        },
        {
            "role": "system",
            "name": "example_assistant",
            "content": "Things working well together will increase revenue.",
        },
        {
            "role": "system",
            "name": "example_user",
            "content": "Let's circle back when we have more bandwidth to touch base on opportunities for increased leverage.",
        },
        {
            "role": "system",
            "name": "example_assistant",
            "content": "Let's talk later when we're less busy about how to do better.",
        },
        {
            "role": "user",
            "content": "This late pivot means we don't have time to boil the ocean for the client deliverable.",
        },
        {
            "role": "user",
            "content": "Our idea seems to be scooped, don't know how to change direction now."
        }
    ]
    print(openai_access.complete_chat(messages, max_tokens=15, n=1, temperature=0.8))
    pass