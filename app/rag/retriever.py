import json
import logging
import os
import re
from dotenv import load_dotenv
import chromadb
from app.core.schemas import PRContext
from google import genai
from google.genai import types
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

load_dotenv()


class CodebaseRetriever:

    def __init__(self):
        self.gemini_client = genai.Client()
        self.chroma_client = chromadb.PersistentClient(path="./codebase_index")
        self._bm25_cache = {}

    def _safe_name(self, repo_name: str) -> str:
        return repo_name.replace("/", "__").replace("-", "_")

    def get_collection(self, repo_name: str):
        collection_name = self._safe_name(repo_name)
        try:
            return self.chroma_client.get_collection(collection_name)
        except Exception:
            return None

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r'[a-zA-Z0-9_]+', text.lower())

    def _load_bm25(self, repo_name: str):
        if repo_name in self._bm25_cache:
            return self._bm25_cache[repo_name]

        corpus_path = f"./codebase_index/bm25_{self._safe_name(repo_name)}.json"
        if not os.path.exists(corpus_path):
            return None

        try:
            with open(corpus_path, "r", encoding="utf-8") as f:
                corpus = json.load(f)

            tokenized = [self._tokenize(doc["text"]) for doc in corpus]
            bm25 = BM25Okapi(tokenized)
            self._bm25_cache[repo_name] = (bm25, corpus)
            logger.info(
                f"[Retriever] Loaded BM25 index ({len(corpus)} docs) for {repo_name}"
            )
            return self._bm25_cache[repo_name]
        except Exception as e:
            logger.warning(f"[Retriever] Failed to load BM25 corpus: {e}")
            return None

    def _build_query_text(self, context: PRContext) -> str:
        parts = [f"PR: {context.title}"]
        for f in context.files:
            if f.patch:
                parts.append(f"File: {f.filename}\n{f.patch[:500]}")
        return "\n\n".join(parts)

    def retrieve_context(self, context: PRContext, n_results: int = 5) -> str:
        collection = self.get_collection(context.repo_name)

        if not collection:
            logger.warning(
                f"[Retriever] No index found for {context.repo_name}. "
                f"Run ingestion first."
            )
            return ""

        query_text = self._build_query_text(context)
        changed_paths = [f.filename for f in context.files]

        # 1. Vector search
        try:
            response = self.gemini_client.models.embed_content(
                model="gemini-embedding-2",
                contents=query_text,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_QUERY"
                )
            )
            query_embedding = response.embeddings[0].values
        except Exception as e:
            logger.error(f"[Retriever] Gemini API embedding failed: {e}")
            query_embedding = None

        vector_n = max(n_results * 3, 15)
        vector_results = None
        if query_embedding:
            try:
                vector_results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=vector_n,
                    where={"filepath": {"$nin": changed_paths}}
                )
            except Exception as e:
                logger.error(f"[Retriever] Vector query failed: {e}")

        # 2. BM25 search
        bm25_data = self._load_bm25(context.repo_name)
        bm25_results = None
        if bm25_data:
            bm25, corpus = bm25_data
            tokenized_query = self._tokenize(query_text)
            scores = bm25.get_scores(tokenized_query)
            scored_indices = sorted(
                enumerate(scores), key=lambda x: x[1], reverse=True
            )[:vector_n]
            bm25_results = [
                (corpus[i]["text"], corpus[i], scores[i])
                for i, score in scored_indices
            ]

        # 3. Fuse with RRF
        fused = {}
        if vector_results and vector_results["documents"][0]:
            for rank, (doc, meta) in enumerate(zip(
                vector_results["documents"][0], vector_results["metadatas"][0]
            )):
                key = f"{meta['filepath']}:{meta['start_line']}-{meta['end_line']}"
                fused[key] = {
                    "text": doc,
                    "filepath": meta["filepath"],
                    "start_line": meta["start_line"],
                    "end_line": meta["end_line"],
                    "rrf": 1.0 / (60 + rank),
                    "source": "vector"
                }

        if bm25_results:
            for rank, (text, meta, score) in enumerate(bm25_results):
                key = f"{meta['filepath']}:{meta['start_line']}-{meta['end_line']}"
                if key in fused:
                    fused[key]["rrf"] += 1.0 / (60 + rank)
                    fused[key]["source"] = "hybrid"
                else:
                    fused[key] = {
                        "text": text,
                        "filepath": meta["filepath"],
                        "start_line": meta["start_line"],
                        "end_line": meta["end_line"],
                        "rrf": 1.0 / (60 + rank),
                        "source": "bm25"
                    }

        if not fused:
            return ""

        sorted_results = sorted(
            fused.values(), key=lambda x: x["rrf"], reverse=True
        )[:n_results]

        for r in sorted_results:
            logger.info(
                f"[Retriever] Chunk: {r['filepath']} "
                f"(lines {r['start_line']}-{r['end_line']}) "
                f"source={r['source']} rrf={r['rrf']:.3f}"
            )

        context_parts = [
            "RELEVANT CODEBASE CONTEXT "
            "(retrieved by hybrid search: vector similarity + keyword matching):"
        ]
        context_parts.append(
            "These files are related to this PR's changes:\n"
        )

        for r in sorted_results:
            context_parts.append(
                f"--- {r['filepath']} "
                f"(lines {r['start_line']}-{r['end_line']}) "
                f"[{r['source']}] ---"
            )
            context_parts.append(r["text"])
            context_parts.append("")

        retrieved_context = "\n".join(context_parts)

        logger.info(
            f"[Retriever] Retrieved {len(sorted_results)} chunks "
            f"for PR #{context.pr_number} "
            f"(vector + BM25 hybrid)"
        )

        return retrieved_context
