"""Thin wrapper over an in-memory Qdrant collection."""
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


class Store:
    def __init__(self, embedder, name="kb"):
        self.embedder = embedder
        self.name = name
        self.client = QdrantClient(":memory:")
        self.client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=embedder.dim, distance=Distance.COSINE),
        )
        self._n = 0

    def add(self, doc_id: str, text: str, poisoned: bool = False):
        self._n += 1
        self.client.upsert(
            collection_name=self.name,
            points=[PointStruct(
                id=self._n,
                vector=self.embedder.encode(text),
                payload={"doc_id": doc_id, "text": text, "poisoned": poisoned},
            )],
        )

    def search(self, query: str, k: int = 3):
        res = self.client.query_points(
            collection_name=self.name, query=self.embedder.encode(query), limit=k
        )
        return [p.payload for p in res.points]
