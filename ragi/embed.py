"""Embeddings. Default is an offline hashed bag-of-words embedder so the project runs with no
model download. Set EMBED=st to use sentence-transformers (all-MiniLM-L6-v2) instead."""
import os
import re
import zlib
import numpy as np

DIM_HASH = 512


class HashEmbedder:
    dim = DIM_HASH

    def encode(self, text: str) -> list[float]:
        v = np.zeros(self.dim, dtype=np.float32)
        for tok in re.findall(r"[a-z0-9']+", text.lower()):
            v[zlib.crc32(tok.encode()) % self.dim] += 1.0
        n = np.linalg.norm(v)
        return (v / n if n else v).tolist()


class STEmbedder:
    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.dim = self.model.get_sentence_embedding_dimension()

    def encode(self, text: str) -> list[float]:
        return self.model.encode(text, normalize_embeddings=True).tolist()


def get_embedder():
    return STEmbedder() if os.environ.get("EMBED") == "st" else HashEmbedder()
