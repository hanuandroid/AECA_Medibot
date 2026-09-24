"""Discover source documents. The parent folder name is the MediAssist collection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.rbac import ALL_COLLECTIONS, Collection

SUPPORTED_SUFFIXES = {".pdf", ".md"}


@dataclass(frozen=True)
class SourceDocument:
    path: Path
    collection: Collection

    @property
    def filename(self) -> str:
        return self.path.name


def discover_documents(data_dir: Path) -> list[SourceDocument]:
    """Return every PDF/Markdown file under ``data_dir/<collection>/``.

    Folders that are not a known collection (e.g. ``db/``) are ignored; a supported file in an
    unknown folder is an error, so nothing is silently indexed with the wrong access roles.
    """
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")
    known = {c.value for c in ALL_COLLECTIONS}
    docs: list[SourceDocument] = []
    for path in sorted(data_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        folder = path.parent.name
        if folder not in known:
            raise ValueError(f"{path} is not inside a known collection folder {sorted(known)}")
        docs.append(SourceDocument(path=path, collection=Collection(folder)))
    return docs
