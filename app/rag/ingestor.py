import os
import ast
import logging
import hashlib
from pathlib import Path
from github import Github
import chromadb
from app.config import settings

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

INDEXABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".java", ".go",
    ".rb", ".rs", ".cpp", ".c", ".cs",
    ".jsx", ".tsx", ".vue", ".swift"
}

SKIP_PATTERNS = [
    "node_modules", "__pycache__", ".git",
    "dist", "build", ".next", "venv",
    "package-lock.json", "yarn.lock",
    ".min.js", ".min.css"
]


class CodebaseIngestor:

    def __init__(self):
        self.github_client = Github(settings.GITHUB_TOKEN)
        self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.chroma_client = chromadb.PersistentClient(path="./codebase_index")

    def get_or_create_collection(self, repo_name: str):
        collection_name = repo_name.replace("/", "__").replace("-", "_")
        return self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"repo": repo_name}
        )

    def ingest_repo(self, repo_name: str, branch: str = "main") -> dict:
        logger.info(f"[Ingestor] Starting ingestion for {repo_name} branch {branch}")

        repo = self.github_client.get_repo(repo_name)
        collection = self.get_or_create_collection(repo_name)

        all_files = self._get_all_files(repo, branch)
        logger.info(f"[Ingestor] Found {len(all_files)} indexable files")

        total_chunks = 0
        for file_path, file_content in all_files.items():
            chunks = self._chunk_file(file_path, file_content)
            if chunks:
                self._store_chunks(collection, repo_name, file_path, chunks)
                total_chunks += len(chunks)

        logger.info(
            f"[Ingestor] Done. Indexed {len(all_files)} files, "
            f"{total_chunks} chunks for {repo_name}"
        )

        return {
            "repo": repo_name,
            "files_indexed": len(all_files),
            "chunks_stored": total_chunks
        }

    def _get_all_files(self, repo, branch: str) -> dict:
        files = {}

        def fetch_contents(path=""):
            try:
                contents = repo.get_contents(path, ref=branch)
                for item in contents:
                    if any(skip in item.path for skip in SKIP_PATTERNS):
                        continue

                    if item.type == "dir":
                        fetch_contents(item.path)
                    elif item.type == "file":
                        ext = Path(item.path).suffix.lower()
                        if ext in INDEXABLE_EXTENSIONS:
                            try:
                                content = item.decoded_content.decode(
                                    "utf-8", errors="ignore"
                                )
                                if len(content) < 100000:
                                    files[item.path] = content
                            except Exception as e:
                                logger.warning(
                                    f"[Ingestor] Could not read {item.path}: {e}"
                                )
            except Exception as e:
                logger.warning(f"[Ingestor] Could not fetch {path}: {e}")

        fetch_contents()
        return files

    def _chunk_file(self, filepath: str, content: str) -> list:
        if filepath.endswith(".py"):
            return self._chunk_python_ast(filepath, content)
        else:
            return self._chunk_by_lines(filepath, content)

    def _chunk_python_ast(self, filepath: str, content: str) -> list:
        chunks = []

        try:
            tree = ast.parse(content)
            lines = content.split("\n")
            seen_ranges = set()

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    start_line = node.lineno - 1
                    end_line = node.end_lineno
                    range_key = (start_line, end_line)

                    if range_key in seen_ranges:
                        continue
                    seen_ranges.add(range_key)

                    chunk_lines = lines[start_line:end_line]
                    chunk_text = "\n".join(chunk_lines)

                    if len(chunk_text.strip()) < 50:
                        continue

                    chunks.append({
                        "text": chunk_text,
                        "filepath": filepath,
                        "start_line": start_line + 1,
                        "end_line": end_line,
                        "type": type(node).__name__,
                        "name": node.name
                    })

        except SyntaxError:
            logger.warning(f"[Ingestor] AST parse failed for {filepath}, using line chunking")
            return self._chunk_by_lines(filepath, content)

        if not chunks and len(content) < 5000:
            chunks.append({
                "text": content,
                "filepath": filepath,
                "start_line": 1,
                "end_line": len(content.split("\n")),
                "type": "module",
                "name": filepath
            })

        return chunks

    def _chunk_by_lines(self, filepath: str, content: str) -> list:
        lines = content.split("\n")
        chunks = []
        chunk_size = 60
        overlap = 10
        i = 0

        while i < len(lines):
            chunk_lines = lines[i:i + chunk_size]
            chunk_text = "\n".join(chunk_lines)

            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text,
                    "filepath": filepath,
                    "start_line": i + 1,
                    "end_line": min(i + chunk_size, len(lines)),
                    "type": "chunk",
                    "name": f"{filepath}:{i+1}"
                })

            i += chunk_size - overlap

        return chunks

    def _store_chunks(self, collection, repo_name: str, filepath: str, chunks: list):
        texts = [c["text"] for c in chunks]

        embeddings = self._get_embeddings_safe(texts)

        if not embeddings:
            logger.error(
                f"[Ingestor] No embeddings returned for {filepath} — skipping"
            )
            return

        if len(embeddings) != len(texts):
            logger.error(
                f"[Ingestor] Mismatch after retries: got {len(embeddings)} "
                f"embeddings for {len(texts)} texts in {filepath} — skipping"
            )
            return

        ids = []
        metadatas = []

        for chunk in chunks:
            unique_str = (
                f"{repo_name}:{chunk['filepath']}:"
                f"{chunk['start_line']}:{chunk['type']}:{chunk['name']}"
            )
            chunk_id = hashlib.md5(unique_str.encode()).hexdigest()
            ids.append(chunk_id)

            metadatas.append({
                "filepath": chunk["filepath"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "type": chunk["type"],
                "name": chunk["name"],
                "repo": repo_name,
            })

        collection.upsert(
            documents=texts,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas,
        )

        logger.info(
            f"[Ingestor] Stored {len(chunks)} chunks for {filepath}"
        )

    def _get_embeddings_safe(self, texts: list[str]) -> list:
        for attempt in range(1, 4):
            try:
                response = self.gemini_client.models.embed_content(
                    model="gemini-embedding-2",
                    contents=texts,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT"
                    )
                )
                embeddings = [emb.values for emb in response.embeddings]

                if len(embeddings) == len(texts):
                    return embeddings

                logger.warning(
                    f"[Ingestor] Embedding count mismatch: got {len(embeddings)} "
                    f"for {len(texts)} texts (attempt {attempt}/3)"
                )

            except Exception as e:
                logger.warning(
                    f"[Ingestor] Embedding API error on attempt {attempt}/3: {e}"
                )

        logger.warning(
            f"[Ingestor] Batch embed failed after 3 attempts. "
            f"Falling back to single embedding calls."
        )
        results = []
        for i, text in enumerate(texts):
            try:
                response = self.gemini_client.models.embed_content(
                    model="gemini-embedding-2",
                    contents=[text],
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT"
                    )
                )
                if response.embeddings:
                    results.append(response.embeddings[0].values)
                else:
                    logger.error(
                        f"[Ingestor] Single embed returned empty for chunk {i}"
                    )
                    return []
            except Exception as e:
                logger.error(
                    f"[Ingestor] Single embed failed for chunk {i}: {e}"
                )
                return []

        return results
