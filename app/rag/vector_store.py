from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from langchain.docstore.document import Document
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings
from huggingface_hub import InferenceClient

from app.config import settings


class HFInferenceEmbeddings(Embeddings):
    """Embeddings adapter backed by Hugging Face Inference API.

    We intentionally call huggingface_hub directly because older LangChain
    wrappers can break on newer HF response formats.
    """

    def __init__(self, api_key: str, model_name: str) -> None:
        self._client = InferenceClient(token=api_key)
        self._model_name = model_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        vector = self._client.feature_extraction(text, model=self._model_name)
        try:
            # HF returns numpy arrays; FAISS expects python float lists.
            return [float(v) for v in vector.tolist()]
        except AttributeError:
            return [float(v) for v in cast(list[float], vector)]


class VectorStoreManager:
    """Stores one FAISS index per file_id on local disk."""

    def __init__(self, vector_dir: Path, embedding_model: str) -> None:
        self._vector_dir = vector_dir
        self._embedding_model = embedding_model
        self._embeddings = None
        if settings.hf_api_token:
            self._embeddings = HFInferenceEmbeddings(
                api_key=settings.hf_api_token,
                model_name=embedding_model,
            )

    def has_index(self, file_id: str) -> bool:
        index_dir = self._index_dir(file_id)
        index_path = index_dir / "index.faiss"
        pickle_path = index_dir / "index.pkl"
        if not (index_path.exists() and pickle_path.exists()):
            return False
        return self._is_index_compatible(file_id)

    def is_enabled(self) -> bool:
        return self._embeddings is not None

    def build_index(self, file_id: str, chunks: list[str], file_name: str) -> None:
        if self._embeddings is None:
            raise RuntimeError("RAG embeddings are disabled because HF_API_TOKEN is not configured")
        docs = [
            Document(
                page_content=chunk,
                metadata={"file_id": file_id, "file_name": file_name, "chunk_index": idx},
            )
            for idx, chunk in enumerate(chunks)
        ]
        vectorstore = FAISS.from_documents(docs, self._embeddings)
        target_dir = self._index_dir(file_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        vectorstore.save_local(str(target_dir))
        self._write_index_meta(file_id)

    def search(self, file_id: str, query: str, top_k: int) -> list[tuple[Document, float]]:
        if self._embeddings is None:
            raise RuntimeError("RAG embeddings are disabled because HF_API_TOKEN is not configured")
        vectorstore = FAISS.load_local(
            str(self._index_dir(file_id)),
            self._embeddings,
            allow_dangerous_deserialization=True,
        )
        return vectorstore.similarity_search_with_score(query=query, k=top_k)

    def _index_dir(self, file_id: str) -> Path:
        return self._vector_dir / file_id

    def _meta_path(self, file_id: str) -> Path:
        return self._index_dir(file_id) / "meta.json"

    def _write_index_meta(self, file_id: str) -> None:
        payload = {"embedding_model": self._embedding_model}
        self._meta_path(file_id).write_text(json.dumps(payload), encoding="utf-8")

    def _is_index_compatible(self, file_id: str) -> bool:
        meta_path = self._meta_path(file_id)
        if not meta_path.exists():
            return False
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return False
        return payload.get("embedding_model") == self._embedding_model
