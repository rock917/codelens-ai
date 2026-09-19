import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Optional, Any
from app.config.settings import settings

class VectorStore:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_client(self):
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIR
            )
        return self._client

    def get_collection(self, repository_id: str):
        client = self.get_client()
        collection_name = f"repo_{repository_id.replace('-', '_')}"
        return client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(
        self,
        repository_id: str,
        chunk_ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]]
    ):
        collection = self.get_collection(repository_id)

        # ChromaDB has batch size limits
        batch_size = 100
        for i in range(0, len(chunk_ids), batch_size):
            collection.add(
                ids=chunk_ids[i:i+batch_size],
                embeddings=embeddings[i:i+batch_size],
                documents=documents[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size]
            )

    def search(
        self,
        repository_id: str,
        query_embedding: List[float],
        n_results: int = 20,
        where: Optional[Dict] = None
    ) -> Dict:
        collection = self.get_collection(repository_id)
        count = collection.count()
        if count == 0:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        n_results = min(n_results, count)

        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"]
        }
        if where:
            kwargs["where"] = where

        return collection.query(**kwargs)

    def delete_repository(self, repository_id: str):
        client = self.get_client()
        collection_name = f"repo_{repository_id.replace('-', '_')}"
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

    def get_chunk_count(self, repository_id: str) -> int:
        try:
            collection = self.get_collection(repository_id)
            return collection.count()
        except Exception:
            return 0

# Singleton instance
vector_store = VectorStore()