from dataclasses import dataclass, field
from pydantic import BaseModel
from typing import List, Optional


@dataclass
class ChangedFile:
    filename: str
    status: str
    additions: int
    deletions: int
    patch: str


@dataclass
class RepoContext:
    name: str
    description: str
    primary_language: str
    languages: str
    file_structure: str
    readme_summary: str
    recent_pr_titles: list = field(default_factory=list)


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
    repo_context: RepoContext = None


class ReviewComment(BaseModel):
    filename: str
    line: int
    issue: str
    suggestion: str
    severity: str


class ReviewResult(BaseModel):
    overall_score: int
    approved: bool
    summary: str
    comments: List[ReviewComment]