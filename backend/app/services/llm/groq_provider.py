from groq import AsyncGroq
from typing import List, Dict, AsyncGenerator
from app.services.llm.base import BaseLLMProvider
from app.config.settings import settings

class GroqProvider(BaseLLMProvider):
    def __init__(self):
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL

    async def chat(
        self,
        messages: List[Dict],
        max_tokens: int = 1000,
        temperature: float = 0.1
    ) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content

    async def stream(
        self,
        messages: List[Dict],
        max_tokens: int = 1000,
        temperature: float = 0.1
    ) -> AsyncGenerator[str, None]:
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

# Singleton
groq_provider = GroqProvider()