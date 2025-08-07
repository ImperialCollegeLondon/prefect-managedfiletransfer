from datetime import datetime
from pathlib import Path


class RemoteAsset:
    """
    Represents a remote asset with its path and last modified time.
    """

    def __init__(self, path: Path, last_modified: datetime, size: int | None = None):
        self.path: Path = path
        self.last_modified: datetime = last_modified
        self.size: int | None = size

    def __repr__(self):
        return f"RemoteAsset(path={self.path}, last_modified={self.last_modified}, size={self.size})"
