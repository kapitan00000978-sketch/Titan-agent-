import os
from pathlib import Path
from typing import Any

try:
    import chromadb
    from chromadb.utils import embedding_functions
    from sentence_transformers import SentenceTransformer
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

class VectorRAG:
    """Advanced Semantic Vector RAG for Titan Agent workspace.
    Uses local embeddings via SentenceTransformers and ChromaDB for persistence.
    """
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.db_path = self.workspace / ".titan_vector_db"
        if HAS_CHROMADB:
            self.client = chromadb.PersistentClient(path=str(self.db_path))
            self.emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            self.collection = self.client.get_or_create_collection(
                name="workspace_rag",
                embedding_function=self.emb_fn
            )
        else:
            self.client = None

    def index_workspace(self) -> str:
        if not HAS_CHROMADB:
            return "Error: chromadb or sentence-transformers is not installed."
        
        indexed_count = 0
        from titan_agent.tools import WorkspaceRAG
        bm25 = WorkspaceRAG(self.workspace)
        
        # Clear old index (simplistic approach for demo)
        try:
            self.client.delete_collection("workspace_rag")
            self.collection = self.client.create_collection("workspace_rag", embedding_function=self.emb_fn)
        except Exception:
            pass

        for rel_path, text in bm25._iter_documents():
            chunks = bm25._chunk_text(text)
            for i, chunk in enumerate(chunks):
                doc_id = f"{rel_path}_{i}"
                self.collection.add(
                    ids=[doc_id],
                    documents=[chunk],
                    metadatas=[{"path": rel_path, "chunk_index": i}]
                )
                indexed_count += 1
        return f"Successfully indexed {indexed_count} chunks from the workspace into VectorDB."

    def search(self, query: str, top_k: int = 5) -> str:
        if not HAS_CHROMADB:
            return "Error: Vector RAG is missing dependencies. Run `pip install chromadb sentence-transformers`."
        
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k
        )
        
        if not results or not results['documents'] or not results['documents'][0]:
            return "No matching context found in the workspace."
            
        docs = results['documents'][0]
        metas = results['metadatas'][0]
        
        out = []
        for i, doc in enumerate(docs):
            meta = metas[i]
            out.append(f"--- FILE: {meta['path']} (chunk {meta['chunk_index']}) ---\n{doc.strip()}\n")
            
        return "\n".join(out)
