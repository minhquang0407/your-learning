import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class LLMConfig:
    provider: str = 'template'
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    timeout: float = 60.0


@dataclass
class LLMRequest:
    system_prompt: str
    user_prompt: str
    temperature: float = 0.1
    max_tokens: int = 4096


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    raw: dict | None = None


class LLMProvider:
    available = False

    def complete(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError


class TemplateFallbackProvider(LLMProvider):
    available = False

    def __init__(self, config=None):
        self.config = config or LLMConfig()

    def complete(self, request: LLMRequest) -> LLMResponse:
        raise RuntimeError('LLM provider is not configured; template fallback should be used.')


class OpenAICompatibleProvider(LLMProvider):
    available = True

    def __init__(self, config: LLMConfig):
        if not config.base_url:
            raise ValueError('SOFTGNN_LLM_BASE_URL is required for openai-compatible provider')
        if not config.model:
            raise ValueError('SOFTGNN_LLM_MODEL is required for openai-compatible provider')
        self.config = config

    def complete(self, request: LLMRequest) -> LLMResponse:
        base_url = self.config.base_url.rstrip('/')
        url = f'{base_url}/chat/completions'
        payload = {
            'model': self.config.model,
            'messages': [
                {'role': 'system', 'content': request.system_prompt},
                {'role': 'user', 'content': request.user_prompt},
            ],
            'temperature': request.temperature,
            'max_tokens': request.max_tokens,
        }
        headers = {'Content-Type': 'application/json'}
        if self.config.api_key:
            headers['Authorization'] = f'Bearer {self.config.api_key}'
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                raw = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace')
            raise RuntimeError(f'LLM provider HTTP {exc.code}: {body[:500]}') from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f'LLM provider request failed: {exc}') from exc
        text = raw.get('choices', [{}])[0].get('message', {}).get('content', '')
        return LLMResponse(text=text, provider='openai-compatible', model=self.config.model, raw=raw)


class GeminiProvider(LLMProvider):
    available = True

    def __init__(self, config: LLMConfig):
        if not config.model:
            raise ValueError('SOFTGNN_LLM_MODEL is required for gemini provider')
        if not config.api_key:
            raise ValueError('SOFTGNN_LLM_API_KEY is required for gemini provider')
        self.config = config

    def complete(self, request: LLMRequest) -> LLMResponse:
        base_url = (self.config.base_url or 'https://generativelanguage.googleapis.com/v1beta').rstrip('/')
        url = f'{base_url}/models/{self.config.model}:generateContent?key={self.config.api_key}'
        prompt = f'{request.system_prompt}\n\n{request.user_prompt}'
        payload = {
            'contents': [
                {
                    'role': 'user',
                    'parts': [{'text': prompt}],
                }
            ],
            'generationConfig': {
                'temperature': request.temperature,
                'maxOutputTokens': request.max_tokens,
                'responseMimeType': 'application/json',
            },
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                raw = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace')
            raise RuntimeError(f'Gemini provider HTTP {exc.code}: {body[:500]}') from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f'Gemini provider request failed: {exc}') from exc
        candidates = raw.get('candidates') or []
        parts = candidates[0].get('content', {}).get('parts', []) if candidates else []
        text = ''.join(part.get('text', '') for part in parts)
        return LLMResponse(text=text, provider='gemini', model=self.config.model, raw=raw)


def load_llm_config(provider=None, base_url=None, model=None, api_key=None, timeout=None):
    provider = provider or os.getenv('SOFTGNN_LLM_PROVIDER') or 'template'
    base_url = base_url or os.getenv('SOFTGNN_LLM_BASE_URL')
    model = model or os.getenv('SOFTGNN_LLM_MODEL')
    api_key = api_key or os.getenv('SOFTGNN_LLM_API_KEY')
    timeout_value = timeout or os.getenv('SOFTGNN_LLM_TIMEOUT') or 60.0
    return LLMConfig(
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=api_key,
        timeout=float(timeout_value),
    )


def build_llm_provider(config: LLMConfig):
    provider = (config.provider or 'template').lower()
    if provider in ('template', 'none', 'offline'):
        return TemplateFallbackProvider(config)
    if provider in ('openai-compatible', 'openai_compatible', 'openai'):
        return OpenAICompatibleProvider(config)
    if provider in ('gemini', 'google', 'google-gemini'):
        return GeminiProvider(config)
    raise ValueError(f'Unsupported LLM provider: {config.provider}')
