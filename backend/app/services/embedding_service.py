from typing import List
from threading import RLock
from app.config.settings import settings

class EmbeddingService:
    _instance = None
    _model = None
    _lock = RLock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load_model(self):
        with self._lock:
            return self._load_model()

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            import torch
            torch.set_num_threads(settings.EMBEDDING_CPU_THREADS)
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
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        with self._lock:
            model = self.load_model()
            texts = [t[:2000] for t in texts]
            embeddings = model.encode(
                texts,
                normalize_embeddings=True,
                batch_size=32 if settings.USE_GPU else 8,
                show_progress_bar=False
            )
            return embeddings.tolist()

# Singleton instance
embedding_service = EmbeddingService()
