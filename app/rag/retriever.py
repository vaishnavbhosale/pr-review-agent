import logging
import os
from dotenv import load_dotenv
import chromadb
from app.core.schemas import PRContext

# 1. Import the Gemini SDK instead of sentence_transformers
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Load environment variables (Make sure your .env file has GEMINI_API_KEY)
load_dotenv()

class CodebaseRetriever:
    """
    Retrieves relevant code from the indexed codebase
    based on semantic similarity to the PR diff using Gemini.
    """

    def __init__(self):
        # 2. Initialize the Gemini client 
        self.gemini_client = genai.Client()
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
        """
        collection = self.get_collection(context.repo_name)

        if not collection:
            logger.warning(
                f"[Retriever] No index found for {context.repo_name}. "
                f"Run ingestion first."
            )
            return ""

        # Build query from PR diff content
        query_parts = []
        query_parts.append(f"PR: {context.title}")

        for f in context.files:
            if f.patch:
                # Take first 500 chars of each diff as query signal
                query_parts.append(f"File: {f.filename}\n{f.patch[:500]}")

        query_text = "\n\n".join(query_parts)

        # 3. Generate the embedding using Gemini
        try:
            response = self.gemini_client.models.embed_content(
                model="gemini-embedding-2",
                contents=query_text,
                config=types.EmbedContentConfig(
                    # Using RETRIEVAL_QUERY because we are searching the DB
                    task_type="RETRIEVAL_QUERY" 
                )
            )
            # Extract the raw float array from the response
            query_embedding = response.embeddings[0].values
            
        except Exception as e:
            logger.error(f"[Retriever] Gemini API embedding failed: {e}")
            return ""

        # Retrieve similar chunks from ChromaDB
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
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