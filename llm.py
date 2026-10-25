import logging
import os

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI

load_dotenv()
logger = logging.getLogger("uvicorn.error")

MODELS = [os.getenv("LLM_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")] + [
    name.strip() for name in os.getenv("LLM_FALLBACK_MODELS", "").split(",") if name.strip()
]


class LLMError(Exception):
    pass


_client = None


def get_client():
    global _client
    if _client is None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise LLMError("Chưa có OPENROUTER_API_KEY trong file .env")
        _client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
            timeout=60,
            max_retries=0,
        )
    return _client


def chat(messages, max_tokens=800, temperature=0.2):
    client = get_client()
    last_error = None

    for model in MODELS:
        try:
            response = client.chat.completions.create(
                model=model, messages=messages, temperature=temperature, max_tokens=max_tokens
            )
        except (APIConnectionError, APIStatusError) as error:
            logger.warning("model=%s lỗi: %s -> thử model tiếp theo", model, error)
            last_error = error
            continue

        answer = response.choices[0].message.content if response.choices else None
        if answer:
            return answer.strip(), response.model, response.usage
        logger.warning("model=%s trả về rỗng -> thử model tiếp theo", model)

    raise LLMError(f"Không gọi được LLM. Lỗi cuối: {last_error}")