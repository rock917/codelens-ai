from sentence_transformers import SentenceTransformer
from typing import List
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

            if settings.USE_GPU:
                import torch
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
                print(f"🖥️ Using device: {device}")
            else:
                device = 'cpu'
                print(f"🖥️ Using device: cpu (production mode)")

            self._model = SentenceTransformer(
                settings.EMBEDDING_MODEL,
                device=device
            )
            print(f"✅ Embedding model loaded on {device}!")
        return self._model

    def embed_text(self, text: str) -> List[float]:
        model = self.load_model()
        text = text[:2000] if len(text) > 2000 else text
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        model = self.load_model()
        texts = [t[:2000] if len(t) > 2000 else t for t in texts]
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=32 if settings.USE_GPU else 8,
            show_progress_bar=False
        )
        return embeddings.tolist()

# Singleton instance
embedding_service = EmbeddingService()