from groq import AsyncGroq
from typing import List, Dict, AsyncGenerator
from app.services.llm.base import BaseLLMProvider
from app.config.settings import settings
import asyncio
from contextlib import asynccontextmanager
from fastapi import HTTPException


@asynccontextmanager
async def model_slot(provider):
    try:
        await asyncio.wait_for(provider.slots.acquire(), timeout=5)
    except asyncio.TimeoutError:
        raise HTTPException(503, 'AI is busy. Please try again shortly.', headers={'Retry-After': '10'})
    try:
        async with asyncio.timeout(90):
            yield
    finally:
        provider.slots.release()

class GroqProvider(BaseLLMProvider):
    def __init__(self):
        self.client = AsyncGroq(
            api_key=settings.GROQ_API_KEY,
            timeout=30.0  # 30 second timeout per request
        )
        self.model = settings.GROQ_MODEL
        self.slots = asyncio.Semaphore(2)

    async def chat(
        self,
        messages: List[Dict],
        max_tokens: int = 1000,
        temperature: float = 0.1
    ) -> str:
        async with model_slot(self):
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=min(max_tokens, 4000),
                temperature=temperature
            )
        return response.choices[0].message.content

    async def stream(
        self,
        messages: List[Dict],
        max_tokens: int = 1000,
        temperature: float = 0.1
    ) -> AsyncGenerator[str, None]:
        async with model_slot(self):
            stream = await self.client.chat.completions.create(
                model=self.model, messages=messages, max_tokens=min(max_tokens, 4000),
                temperature=temperature, stream=True,
            )
            try:
                async for chunk in stream:
                    if chunk.choices:
                        delta = chunk.choices[0].delta.content
                        if delta:
                            yield delta
            finally:
                await stream.close()

# Singleton
groq_provider = GroqProvider()
