"""Provider-agnostic LLM layer (architecture: AssessmentProvider interface).

GoogleProvider calls Gemini with model fallback + retry so real LLM responses
are returned even when one model is retired or overloaded.
"""
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMResult(BaseModel):
    data: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    error: Optional[str] = None


class AssessmentProvider(ABC):
    @abstractmethod
    def generate_json(self, prompt: str, schema: Optional[Type[BaseModel]] = None) -> LLMResult: ...

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]: ...


class GoogleProvider(AssessmentProvider):
    def _models(self) -> List[str]:
        chain = [settings.GEMINI_MODEL] + [
            m.strip() for m in settings.GEMINI_FALLBACK_MODELS.split(",") if m.strip()
        ]
        seen, out = set(), []
        for m in chain:
            if m not in seen:
                seen.add(m)
                out.append(m)
        return out

    def get_model_info(self) -> Dict[str, Any]:
        return {"provider": "google", "models": self._models(), "configured": bool(settings.GEMINI_API_KEY)}

    def generate_json(self, prompt: str, schema: Optional[Type[BaseModel]] = None) -> LLMResult:
        if not settings.GEMINI_API_KEY:
            return LLMResult(error="GEMINI_API_KEY not configured")
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            cfg: Dict[str, Any] = {"response_mime_type": "application/json", "temperature": 0.1}
            if schema is not None:
                cfg["response_schema"] = schema
            last_err = "unknown error"
            for model in self._models():
                for attempt in range(settings.LLM_MAX_RETRIES + 1):
                    try:
                        resp = client.models.generate_content(
                            model=model, contents=prompt, config=types.GenerateContentConfig(**cfg)
                        )
                        return LLMResult(data=json.loads(resp.text), model=model)
                    except json.JSONDecodeError as e:
                        last_err = f"{model}: invalid JSON ({e})"
                        break
                    except Exception as e:  # noqa: BLE001
                        last_err = f"{model}: {str(e)[:200]}"
                        msg = str(e)
                        if "503" in msg or "UNAVAILABLE" in msg:
                            time.sleep(1.5 * (attempt + 1))
                            continue
                        break
                logger.warning("Gemini model failed, trying next: %s", last_err)
            return LLMResult(error=last_err)
        except Exception as e:
            return LLMResult(error=f"Gemini client error: {e}")


class GroqProvider(AssessmentProvider):
    _deprioritized_models: set = set()

    def _models(self) -> List[str]:
        chain = [settings.GROQ_MODEL] + [
            m.strip() for m in settings.GROQ_FALLBACK_MODELS.split(",") if m.strip()
        ]
        seen, active, deprioritized = set(), [], []
        for m in chain:
            if m not in seen:
                seen.add(m)
                if m in self._deprioritized_models:
                    deprioritized.append(m)
                else:
                    active.append(m)
        return active + deprioritized

    def get_model_info(self) -> Dict[str, Any]:
        return {"provider": "groq", "models": self._models(), "configured": bool(settings.GROQ_API_KEY)}

    def generate_json(self, prompt: str, schema: Optional[Type[BaseModel]] = None) -> LLMResult:
        if not settings.GROQ_API_KEY:
            return LLMResult(error="GROQ_API_KEY not configured")
        import httpx
        import re

        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
        last_err = "unknown error"
        for model in self._models():
            for attempt in range(settings.LLM_MAX_RETRIES + 1):
                try:
                    payload: Dict[str, Any] = {
                        "model": model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a precise JSON-only extraction and evaluation assistant. Output valid JSON only, without markdown fences or additional commentary.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.1,
                    }
                    with httpx.Client(timeout=40.0) as client:
                        resp = client.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers=headers,
                            json=payload,
                        )
                    if resp.status_code == 200:
                        data_json = resp.json()
                        raw_content = data_json["choices"][0]["message"]["content"]
                        # Strip accidental think tags from reasoning models
                        clean_content = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL).strip()
                        # Strip accidental markdown code blocks if any
                        if "```" in clean_content:
                            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean_content, flags=re.DOTALL)
                            if match:
                                clean_content = match.group(1).strip()
                            else:
                                clean_content = clean_content.split("```", 1)[-1]
                                if clean_content.startswith("json"):
                                    clean_content = clean_content[4:].strip()
                                if clean_content.endswith("```"):
                                    clean_content = clean_content.rsplit("```", 1)[0].strip()
                        parsed = json.loads(clean_content)
                        return LLMResult(data=parsed, model=model)
                    last_err = f"{model} status {resp.status_code}: {resp.text[:200]}"
                    if resp.status_code == 429:
                        resp_lower = resp.text.lower()
                        # If daily token limit (TPD) was reached, retrying immediately is futile
                        if "tpd" in resp_lower or "tokens per day" in resp_lower or "limit 200000" in resp_lower:
                            self._deprioritized_models.add(model)
                            break
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    if resp.status_code == 503:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    break
                except json.JSONDecodeError as e:
                    last_err = f"{model}: invalid JSON ({e})"
                    break
                except Exception as e:
                    last_err = f"{model}: {str(e)[:200]}"
                    time.sleep(1.0)
            logger.warning("Groq model failed, trying next: %s", last_err)
        return LLMResult(error=last_err)


def get_provider() -> AssessmentProvider:
    provider_pref = (settings.LLM_PROVIDER or "auto").lower()
    if provider_pref == "groq":
        return GroqProvider()
    if provider_pref == "google":
        return GoogleProvider()
    # auto: prefer Groq if GROQ_API_KEY is present, else Google if GEMINI_API_KEY is present
    if settings.GROQ_API_KEY:
        return GroqProvider()
    if settings.GEMINI_API_KEY:
        return GoogleProvider()
    # fallback to GroqProvider default
    return GroqProvider()

