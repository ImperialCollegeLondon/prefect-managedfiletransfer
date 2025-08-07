from datetime import timedelta
from pydantic import BaseModel, Field
from prefect_managedfiletransfer.SortFilesBy import SortFilesBy

from pathlib import Path


class FileMatcher(BaseModel):
    """
    Represents a file matcher with a source path and a pattern to match files.
    This is used to find files in a directory that match a specific pattern.
    """

    source_folder: Path = Field(
        default=Path("."),
        description="Path to the source directory to look for files.",
    )
    pattern_to_match: str = Field(
        default="*",
        description="Pattern to match files in the source directory. Supports glob patterns like '*.txt' or 'file_*.csv'.",
    )
    minimum_age: str | int | timedelta | None = Field(
        default=None,
        description="Only transfer files older than this in secs (or other time with suffix s|m|h|d|w|month|year). Default off.",
    )
    maximum_age: str | int | timedelta | None = Field(
        default=None,
        description="Only transfer files newer than this in secs (or other time with suffix s|m|h|d|w|month|year). Default off.",
    )
    sort: SortFilesBy = Field(
        default=SortFilesBy.PATH_ASC,
        description="Sort files by a specific attribute. Default is PATH_ASC.",
    )
    skip: int = Field(
        default=0,
        description="Number of files to skip in the sorted list. Default is 0.",
    )
    take: int | None = Field(
        default=None,
        description="Number of files to take from the sorted list. If None, all files are taken. Default is None.",
    )
