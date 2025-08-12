from datetime import datetime
from pathlib import Path


class AssetDownloadResult:
    """
    Represents the result of an asset download operation.
    """

    def __init__(
        self,
        success: bool,
        file_path: Path | None,
        download_skipped: bool = False,
        last_modified: datetime | None = None,
        size: int = 0,
        error: str | None = None,
    ):
        """
        Represents the result of an asset download operation.
        :param success: True if the download was successful, False otherwise.
        :param file_path: The path to the downloaded file, or None if the download failed.
        :param download_skipped: True if the download was skipped because the file was not newer than the destination file.
        :param last_modified: The last modified time of the file, if available.
        """
        self.last_modified = last_modified
        self.success = success
        self.file_path = file_path
        self.download_skipped = download_skipped
        self.error = error
        self.size = size

        if not success and file_path is not None:
            raise ValueError("If success is False, file_path must be None")

    def __repr__(self):
        if self.error:
            return f"AssetDownloadResult(success={self.success}, error={self.error})"

        return f"AssetDownloadResult(success={self.success}, file_path={self.file_path}, download_skipped={self.download_skipped}, last_modified={self.last_modified})"
