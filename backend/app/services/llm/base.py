from abc import ABC, abstractmethod
from typing import List, Dict, AsyncGenerator

class BaseLLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: List[Dict],
        max_tokens: int = 1000,
        temperature: float = 0.1
    ) -> str:
        pass

    @abstractmethod
    async def stream(
        self,
        messages: List[Dict],
        max_tokens: int = 1000,
        temperature: float = 0.1
    ) -> AsyncGenerator[str, None]:
        pass