import os
import ast
import logging
import hashlib
from pathlib import Path
from github import Github
from sentence_transformers import SentenceTransformer
import chromadb
from app.config import settings

logger = logging.getLogger(__name__)

# Files worth indexing for code review context
INDEXABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".java", ".go",
    ".rb", ".rs", ".cpp", ".c", ".cs",
    ".jsx", ".tsx", ".vue", ".swift"
}

# Files to skip
SKIP_PATTERNS = [
    "node_modules", "__pycache__", ".git",
    "dist", "build", ".next", "venv",
    "package-lock.json", "yarn.lock",
    ".min.js", ".min.css"
]


class CodebaseIngestor:
    """
    Ingests a GitHub repository's codebase into ChromaDB.

    Splits code files into function-level chunks using AST parsing
    so we never split a function in half. Falls back to line-based
    chunking for non-Python files.

    This runs once per repo and updates when main branch changes.
    """

    def __init__(self):
        self.github_client = Github(settings.GITHUB_TOKEN)
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.chroma_client = chromadb.PersistentClient(path="./codebase_index")

    def get_or_create_collection(self, repo_name: str):
        """
        Each repository gets its own ChromaDB collection.
        Collection name is sanitised repo name.
        """
        collection_name = repo_name.replace("/", "__").replace("-", "_")
        return self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"repo": repo_name}
        )

    def ingest_repo(self, repo_name: str, branch: str = "main") -> dict:
        """
        Main entry point. Fetches all code files from the repo
        and indexes them into ChromaDB.
        """
        logger.info(f"[Ingestor] Starting ingestion for {repo_name} branch {branch}")

        repo = self.github_client.get_repo(repo_name)
        collection = self.get_or_create_collection(repo_name)

        # Get all files recursively
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
        """
        Recursively fetches all indexable code files from the repo.
        Returns dict of filepath -> content.
        """
        files = {}

        def fetch_contents(path=""):
            try:
                contents = repo.get_contents(path, ref=branch)
                for item in contents:
                    # Skip unwanted patterns
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
                                # Skip very large files
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
        """
        Splits a file into meaningful chunks.

        For Python files: uses AST to split by function and class.
        This ensures we never cut a function in half — the AI
        always sees complete, runnable code units.

        For other files: falls back to line-based chunking with overlap.
        """
        if filepath.endswith(".py"):
            return self._chunk_python_ast(filepath, content)
        else:
            return self._chunk_by_lines(filepath, content)

    def _chunk_python_ast(self, filepath: str, content: str) -> list:
        """
        Uses Python's built-in AST module to extract complete
        functions and classes as chunks.

        Why AST and not character splitting:
        Character splitting at 500 chars might cut a function at line 8
        of a 20-line function. The AI then sees broken, unrunnable code.
        AST splitting gives the AI complete, syntactically valid units.
        """
        chunks = []

        try:
            tree = ast.parse(content)
            lines = content.split("\n")

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    # Get start and end line numbers
                    start_line = node.lineno - 1
                    end_line = node.end_lineno

                    # Extract the complete function or class
                    chunk_lines = lines[start_line:end_line]
                    chunk_text = "\n".join(chunk_lines)

                    # Skip tiny stubs
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
            # If AST parsing fails, fall back to line chunking
            logger.warning(f"[Ingestor] AST parse failed for {filepath}, using line chunking")
            return self._chunk_by_lines(filepath, content)

        # Also add the full file as one chunk for file-level context
        if len(content) < 5000:
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
        """
        Simple line-based chunking with overlap for non-Python files.
        chunk_size=60 lines, overlap=10 lines.
        """
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

    def _store_chunks(
        self,
        collection,
        repo_name: str,
        filepath: str,
        chunks: list
    ):
        """
        Embeds and stores chunks in ChromaDB.
        Uses upsert so re-ingesting the same file never creates duplicates.
        """
        texts = [c["text"] for c in chunks]
        embeddings = self.embedding_model.encode(texts).tolist()

        ids = []
        metadatas = []

        for chunk in chunks:
            # Create a stable unique ID from repo + filepath + position
            chunk_id = hashlib.md5(
                f"{repo_name}:{chunk['filepath']}:{chunk['start_line']}".encode()
            ).hexdigest()
            ids.append(chunk_id)
            metadatas.append({
                "filepath": chunk["filepath"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "type": chunk["type"],
                "name": chunk["name"],
                "repo": repo_name
            })

        collection.upsert(
            documents=texts,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas
        )