import asyncio
import time
import aiohttp
from app.config import settings


class LLMService:
    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        tier1_model: str = "qwen-turbo",
        tier2_model: str = "qwen-plus",
        tier3_model: str = "qwen-max",
        timeout: int = 30,
        max_retries: int = 2,
        circuit_breaker_threshold: int = 5,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.tier1_model = tier1_model
        self.tier2_model = tier2_model
        self.tier3_model = tier3_model
        self.timeout = timeout
        self.max_retries = max_retries
        self._circuit_breaker_threshold = circuit_breaker_threshold
        self._consecutive_failures = 0
        self._circuit_open = False
        self._circuit_open_time = 0.0
        self._CIRCUIT_PROBE_INTERVAL = 600

    def _get_model(self, tier: str) -> str:
        return {
            "tier1": self.tier1_model,
            "tier2": self.tier2_model,
            "tier3": self.tier3_model,
        }[tier]

    def _get_degraded_tier(self, tier: str):
        return {"tier3": "tier2", "tier2": "tier1"}.get(tier)

    async def _raw_call(self, model: str, messages: list, **kwargs) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": model, "messages": messages, **kwargs}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def call(self, tier: str, prompt: str, system_prompt: str = "") -> str:
        if self._circuit_open:
            if time.time() - self._circuit_open_time > self._CIRCUIT_PROBE_INTERVAL:
                self._circuit_open = False
            else:
                raise Exception("Circuit breaker open")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        model = self._get_model(tier)
        delays = [2, 5]

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._raw_call(model, messages)
                self._consecutive_failures = 0
                self._circuit_open = False
                return response["choices"][0]["message"]["content"]
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(delays[min(attempt, len(delays) - 1)])

        degraded = self._get_degraded_tier(tier)
        if degraded:
            degraded_model = self._get_model(degraded)
            try:
                response = await self._raw_call(degraded_model, messages)
                self._consecutive_failures = 0
                return response["choices"][0]["message"]["content"]
            except Exception:
                pass

        self._consecutive_failures += 1
        if self._consecutive_failures >= self._circuit_breaker_threshold:
            self._circuit_open = True
            self._circuit_open_time = time.time()
        raise last_error

    async def call_json(self, tier: str, prompt: str, system_prompt: str = "") -> dict:
        import json

        content = await self.call(tier, prompt, system_prompt)
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(content)


def create_llm_service() -> LLMService:
    return LLMService(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        tier1_model=settings.llm_tier1_model,
        tier2_model=settings.llm_tier2_model,
        tier3_model=settings.llm_tier3_model,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        circuit_breaker_threshold=settings.llm_circuit_breaker_threshold,
    )


llm_service = create_llm_service()
