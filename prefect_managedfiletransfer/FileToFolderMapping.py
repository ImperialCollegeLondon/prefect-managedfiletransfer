from pydantic import BaseModel, Field

from pathlib import Path

from prefect_managedfiletransfer.RemoteAsset import RemoteAsset

import logging

logger = logging.getLogger(__name__)


class FileToFolderMapping(BaseModel):
    source_path_pattern_to_match: str = Field(
        default="*",
        description="Pattern to match files against in the source directory. Supports glob patterns. E.g. 'folder/*.txt' or '*path*/file.*'",
    )

    destination_folder: Path = Field(
        default=Path("."),
        description="Path of the destination folder files matching the pattern should be placed into",
    )

    def is_match(self, file_path: Path) -> bool:
        """
        Check if the given file path matches the source path pattern.
        """

        if not self.source_path_pattern_to_match:
            return False

        if not file_path:
            return False

        return file_path.match(self.source_path_pattern_to_match)

    # define constructor to allow for easy instantiation
    def __init__(
        self,
        source_path_pattern_to_match: str = "*",
        destination_folder: str = ".",
    ):
        super().__init__(
            source_path_pattern_to_match=source_path_pattern_to_match,
            destination_folder=Path(destination_folder),
        )

    @staticmethod
    def apply_mappings(
        mappings: list["FileToFolderMapping"],
        source_files: list[RemoteAsset],
        destination_path,
    ) -> list[tuple[RemoteAsset, Path]]:
        source_destination_pairs = []
        for remote_asset in source_files:
            logger.info(f"Found file: {remote_asset}")

            # calculate the destination path - target + mapping
            target_file_path: Path | None = None

            for mapping in mappings:
                if mapping.is_match(remote_asset.path):
                    if not destination_path:
                        target_file_path = (
                            mapping.destination_folder / remote_asset.path.name
                        )
                    elif (
                        not mapping.destination_folder
                        or mapping.destination_folder == Path(".")
                    ):
                        target_file_path = destination_path / remote_asset.path.name
                    else:
                        target_file_path = (
                            destination_path
                            / mapping.destination_folder
                            / remote_asset.path.name
                        )
                    logger.info(
                        f"File {remote_asset.path} matched {mapping.source_path_pattern_to_match} -> {mapping.destination_folder}"
                    )
                    break

            if not target_file_path:
                logger.info(
                    f"No mapping found for {remote_asset.path}, using default destination path"
                )
                target_file_path = destination_path / remote_asset.path.name

            assert target_file_path is not None

            source_destination_pairs.append((remote_asset, target_file_path))

        return source_destination_pairs
