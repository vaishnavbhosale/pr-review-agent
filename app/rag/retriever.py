import logging
from sentence_transformers import SentenceTransformer
import chromadb
from app.core.schemas import PRContext

logger = logging.getLogger(__name__)


class CodebaseRetriever:
    """
    Retrieves relevant code from the indexed codebase
    based on semantic similarity to the PR diff.

    When a PR modifies jwt.py, this finds other files
    in the codebase that are semantically related to
    JWT handling — imports, usages, related auth code.
    """

    def __init__(self):
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.chroma_client = chromadb.PersistentClient(path="./codebase_index")

    def get_collection(self, repo_name: str):
        collection_name = repo_name.replace("/", "__").replace("-", "_")
        try:
            return self.chroma_client.get_collection(collection_name)
        except Exception:
            return None

    def retrieve_context(self, context: PRContext, n_results: int = 5) -> str:
        """
        Takes the PR diff and retrieves the most semantically
        similar code from the indexed codebase.

        Returns formatted context string ready to inject into prompt.
        """
        collection = self.get_collection(context.repo_name)

        if not collection:
            logger.warning(
                f"[Retriever] No index found for {context.repo_name}. "
                f"Run ingestion first."
            )
            return ""

        # Build query from PR diff content
        # We combine all diff patches to create a rich query
        query_parts = []
        query_parts.append(f"PR: {context.title}")

        for f in context.files:
            if f.patch:
                # Take first 500 chars of each diff as query signal
                query_parts.append(f"File: {f.filename}\n{f.patch[:500]}")

        query_text = "\n\n".join(query_parts)

        # Embed the query
        query_embedding = self.embedding_model.encode(query_text).tolist()

        # Retrieve similar chunks
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                # Exclude files that are already in the PR diff
                # (we already have those, no need to retrieve them)
                where={"filepath": {
                    "$nin": [f.filename for f in context.files]
                }}
            )
        except Exception as e:
            logger.error(f"[Retriever] Query failed: {e}")
            return ""

        if not results["documents"][0]:
            return ""

        # Format retrieved chunks as context
        context_parts = ["RELEVANT CODEBASE CONTEXT (retrieved by semantic similarity):"]
        context_parts.append("These files are semantically related to this PR's changes:\n")

        for i, (doc, metadata) in enumerate(
            zip(results["documents"][0], results["metadatas"][0])
        ):
            context_parts.append(
                f"--- {metadata['filepath']} "
                f"(lines {metadata['start_line']}-{metadata['end_line']}) ---"
            )
            context_parts.append(doc)
            context_parts.append("")

        retrieved_context = "\n".join(context_parts)

        logger.info(
            f"[Retriever] Retrieved {len(results['documents'][0])} "
            f"relevant chunks for PR #{context.pr_number}"
        )

        return retrieved_context