def safe_collection_name(repo_name: str) -> str:
    return repo_name.replace("/", "__").replace("-", "_")
