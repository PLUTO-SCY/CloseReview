import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMError(RuntimeError):
    pass


def llm_configured() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY"))


def llm_model() -> str:
    return os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")


def chat_completion(messages: list[dict], temperature: float = 0.2) -> str:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise LLMError("Missing DEEPSEEK_API_KEY. Add it to `.env.local` and restart PaperTrail.")

    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": llm_model(),
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if os.environ.get("DEEPSEEK_THINKING", "enabled").lower() not in ("0", "false", "off", "disabled"):
        payload["reasoning_effort"] = os.environ.get("DEEPSEEK_REASONING_EFFORT", "high")
        payload["thinking"] = {"type": "enabled"}

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=int(os.environ.get("LLM_TIMEOUT_SECONDS", "90"))) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMError(f"LLM request failed with HTTP {exc.code}: {detail[:500]}") from exc
    except (URLError, TimeoutError) as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LLMError("LLM returned invalid JSON.") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("LLM response did not include a message.") from exc
    if not content:
        raise LLMError("LLM returned an empty response.")
    return content.strip()
