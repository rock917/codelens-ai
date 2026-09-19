from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np
from app.config.settings import settings

class EmbeddingService:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load_model(self):
        if self._model is None:
            print(f"⏳ Loading embedding model: {settings.EMBEDDING_MODEL}")
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            print(f"✅ Embedding model loaded!")
        return self._model

    def embed_text(self, text: str) -> List[float]:
        model = self.load_model()
        # Truncate long text
        text = text[:2000] if len(text) > 2000 else text
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        model = self.load_model()
        # Truncate long texts
        texts = [t[:2000] if len(t) > 2000 else t for t in texts]
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False
        )
        return embeddings.tolist()

# Singleton instance
embedding_service = EmbeddingService()