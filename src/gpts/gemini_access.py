import os
import json
import google.generativeai as genai
import typing
import sys
root_dir = f"{__file__.split('src')[0]}"
if root_dir not in sys.path:
    sys.path.append(root_dir)
class GeminiAccess(object):
    gemini_model_info = {
        "gemini-1.5-pro": {
            "token_limit_per_min": 2 * 10**6,  # Placeholder - need to find actual Gemini limits
            "request_limit_per_min": 360,  # Placeholder
            "max_token_per_prompt": 2097152  # Up to 32k tokens for Gemini Pro
        },
        # Add more Gemini models here as needed
    }
    def __init__(self, api_key_file: str = ".secrets/google_key.json", model_name: str = "gemini-pro"):
        with open(api_key_file, "r") as f:
            api_key = json.load(f)["api_key"]
        genai.configure(api_key=api_key)

        self.models_supported = list(self.gemini_model_info.keys())
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

        # Initialize or continue the ChatSession
        model = genai.GenerativeModel(model_name=model_name)
        generation_config = genai.types.GenerationConfig(
            # Only one candidate for now.
            candidate_count=n,
            stop_sequences=stop,
            max_output_tokens=max_tokens,
            temperature=temperature)
        for message in messages:
            if "content" in message:
                message["parts"] = message.pop("content")
            if message["role"] == "system":
                message["role"] = "user"
        # Send the message and get the response
        response = model.generate_content(messages, generation_config=generation_config)

        # Process response
        return_responses = [{"role": "assistant", "content": message.content.parts[0].text}
                            for message in response.candidates if message.content.role == "model"]
        # Update usage
        usage_metadata = response.usage_metadata
        self.usage["prompt_tokens"] += usage_metadata.prompt_token_count
        self.usage["completion_tokens"] += usage_metadata.candidates_token_count
        self.usage["total_tokens"] += usage_metadata.total_token_count
        for i in range(len(return_responses) - 1):
            return_responses[i]["finish_reason"] = "stop"
        if len(response.candidates) > 0:
            return_responses[-1]["finish_reason"] = response.candidates[-1].finish_reason
        usage_dict = {
            "prompt_tokens": usage_metadata.prompt_token_count,
            "completion_tokens": usage_metadata.candidates_token_count,
            "total_tokens": usage_metadata.total_token_count,
            "reason": response.candidates[-1].finish_reason if len(response.candidates) > 0 else "stop"
        }
        return return_responses, usage_dict

    def num_tokens_from_messages(self, messages, model=None):
        model = model if model is not None else self.model_name

        if model.startswith("gemini"):
            gen_model = genai.GenerativeModel(model_name=model)

            prompt = ""
            for message in messages:
                prompt += f"{message['role']}: {message['content']}\n"  # Format as a continuous prompt

            response = gen_model.count_tokens(prompt)
            return response.total_tokens
        else:
            raise NotImplementedError(
                f"num_tokens_from_messages() is only implemented for Gemini models, not {model}"
            )
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