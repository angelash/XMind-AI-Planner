from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from app.services.document_store import create_document
from app.services.markdown_import import import_markdown


@dataclass
class MarkdownDirectoryImportFile:
    path: str
    markdown: str
    title: str | None = None


@dataclass
class MarkdownDirectoryImportResult:
    path: str
    title: str | None
    status: str
    document: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "title": self.title,
            "status": self.status,
        }
        if self.document is not None:
            payload["document"] = self.document
        if self.error is not None:
            payload["error"] = self.error
        return payload


@dataclass
class MarkdownDirectoryImportStats:
    total: int = 0
    created: int = 0
    failed: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "created": self.created,
            "failed": self.failed,
        }


def import_markdown_directory(
    files: list[MarkdownDirectoryImportFile],
    owner_id: str | None = None,
) -> tuple[list[MarkdownDirectoryImportResult], MarkdownDirectoryImportStats]:
    if not files:
        raise ValueError("files must not be empty")

    stats = MarkdownDirectoryImportStats(total=len(files))
    results: list[MarkdownDirectoryImportResult] = []

    for file in files:
        try:
            root = import_markdown(file.markdown, file.title)
            document_title = _resolve_document_title(file, root)
            document = create_document(document_title, root, owner_id)
            results.append(
                MarkdownDirectoryImportResult(
                    path=file.path,
                    title=document_title,
                    status="created",
                    document=document,
                )
            )
            stats.created += 1
        except ValueError as exc:
            results.append(
                MarkdownDirectoryImportResult(
                    path=file.path,
                    title=file.title,
                    status="failed",
                    error=str(exc),
                )
            )
            stats.failed += 1

    return results, stats


def _resolve_document_title(file: MarkdownDirectoryImportFile, root: dict[str, Any]) -> str:
    title = str(root.get("text") or "").strip()
    if title:
        return title

    if file.title and file.title.strip():
        return file.title.strip()

    filename = PurePosixPath(file.path).name.strip()
    if filename:
        stem = PurePosixPath(filename).stem.strip()
        if stem:
            return stem

    return "Imported Mindmap"
