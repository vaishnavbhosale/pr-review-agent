from dataclasses import dataclass, field


@dataclass
class ChangedFile:
    filename: str
    status: str
    additions: int
    deletions: int
    patch: str


@dataclass
class PRContext:
    repo_name: str
    pr_number: int
    title: str
    description: str
    author: str
    base_branch: str
    head_branch: str
    files: list = field(default_factory=list)