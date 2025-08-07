from datetime import datetime
from pathlib import Path
from prefect.runtime import flow_run
from prefect_managedfiletransfer.transfer_files_flow import transfer_files_flow
from prefect_managedfiletransfer.AssetDownloadResult import AssetDownloadResult
from prefect_managedfiletransfer.FileToFolderMapping import FileToFolderMapping
from prefect_managedfiletransfer.FileMatcher import FileMatcher
from prefect_managedfiletransfer.RCloneConfigFileBlock import RCloneConfigFileBlock
from prefect_managedfiletransfer.ServerWithBasicAuthBlock import (
    ServerWithBasicAuthBlock,
)
from prefect_managedfiletransfer.ServerWithPublicKeyAuthBlock import (
    ServerWithPublicKeyAuthBlock,
)
from prefect_managedfiletransfer.constants import CONSTANTS
from prefect_managedfiletransfer.TransferType import TransferType
from prefect import flow, get_run_logger
from prefect.filesystems import LocalFileSystem
import shutil
import logging


logger = logging.getLogger(__name__)


def generate_flow_run_name() -> str:
    parameters = flow_run.parameters
    source = parameters["source_block"]
    dest = parameters["destination_block"]
    source_file_matchers: list[FileMatcher] = parameters["source_file_matchers"]
    destination_folder = parameters["destination_folder"]
    mode = parameters["mode"]
    mode_str = mode.name

    if hasattr(source, "host"):
        source = f"{source.host}:{source.port}"
    else:
        source = str(source)

    if hasattr(dest, "host"):
        dest = f"{dest.host}:{dest.port}"
    else:
        dest = str(dest)

    if len(source_file_matchers) == 1:
        source += f":{source_file_matchers[0].source_folder}/{source_file_matchers[0].pattern_to_match}"

    return f"Unpack-{mode_str}-{source}-to-{dest}:{destination_folder}"


@flow(
    name=CONSTANTS.FLOW_NAMES.UNPACK_FILES,
    log_prints=True,
    flow_run_name=generate_flow_run_name,
    retries=2,
    retry_delay_seconds=60 * 20,  # retry every 20 minutes
    timeout_seconds=60 * 30,  # timeout after 30 minutes
)
# like transfer but also unzips/untars etc files
async def unpack_files_flow(
    source_block: (
        ServerWithBasicAuthBlock
        | ServerWithPublicKeyAuthBlock
        | LocalFileSystem
        | RCloneConfigFileBlock
    ),
    destination_block: (
        ServerWithBasicAuthBlock
        | ServerWithPublicKeyAuthBlock
        | LocalFileSystem
        | RCloneConfigFileBlock
    ),
    source_file_matchers: list[FileMatcher] = [FileMatcher()],
    path_mapping: list[FileToFolderMapping] = [],
    destination_folder: Path = Path("."),
    # if true skip files that are newer on the destination
    update_only_if_newer_mode: bool = False,
    overwrite: bool = False,
    mode: TransferType = TransferType.Copy,
    empty_destination_before_unpack: bool = True,
    delete_after_unpack: bool = False,
    reference_date: datetime | None = None,  # defaults to now()
) -> tuple[list[AssetDownloadResult], list[Path]]:
    """
    Unpacks files from a source to a destination, handling various file formats.

    Destination must be a LocalFileSystem.
    uses `transfer_files_flow` to download files and then unpacks them using `shutil.unpack_archive`.
    Args:
        source_block: The source block to transfer files from.
        destination_block: The destination block to transfer files to.
        source_file_matchers: List of file matchers to filter files in the source.
        path_mapping: List of file to folder mappings for transferring files.
        destination_folder: The folder where files will be unpacked on the destination.
        update_only_if_newer_mode: If true, skip files that are newer on the destination.
        overwrite: If true, overwrite the file if it already exists at the destination.
        mode: The transfer mode to use, e.g. Copy or Move.
        empty_destination_before_unpack: If true, delete all files in the destination folder before unpacking.
        delete_after_unpack: If true, delete the original file after unpacking.
        reference_date: The date to use for filtering files, defaults to now() in UTC. Use in testing.
    Returns:
        A tuple containing:
            - A list of AssetDownloadResult objects for the downloaded files.
            - A list of Paths for the unpacked zip/tar/etc files. They may have already been deleted if `delete_after_unpack` is True.
    Raises:
        ValueError: If the destination block is not a LocalFileSystem.
    """

    if not isinstance(destination_block, LocalFileSystem):
        raise ValueError(
            "Unpack files flow only supports LocalFileSystem as destination block."
        )
    logger = get_run_logger()

    download_results: list[AssetDownloadResult] = await transfer_files_flow.fn(
        source_block=source_block,
        destination_block=destination_block,
        source_file_matchers=source_file_matchers,
        path_mapping=path_mapping,
        destination_folder=destination_folder,
        update_only_if_newer_mode=update_only_if_newer_mode,
        overwrite=overwrite,
        mode=mode,
        reference_date=reference_date,
        check_for_space=True,
    )

    if not download_results:
        logger.info("No files downloaded, nothing to unpack.")
        return [], []

    # get the list of file extensions we know how to unpack
    unpackable_extensions = [
        ext for format_meta in shutil.get_unpack_formats() for ext in format_meta[1]
    ]

    logger.debug(f"Unpackable extensions: {unpackable_extensions}")

    unpacked_files = []

    for downloaded in download_results:
        if not downloaded.success or not downloaded.file_path:
            logger.warning(
                f"Download failed for {downloaded.file_path}. Skipping unpack."
            )
            continue
        if downloaded.download_skipped:
            logger.info(
                f"Download skipped for {downloaded.file_path}. Skipping unpack."
            )
            continue

        assert isinstance(downloaded.file_path, Path)
        assert downloaded.file_path is not None

        if not downloaded.file_path.exists():
            logger.warning(
                f"File {downloaded.file_path} does not exist. Skipping unpack."
            )
            continue

        folder = downloaded.file_path.parent
        filename = downloaded.file_path.name

        unpackable = False
        for ext in unpackable_extensions:
            if filename.endswith(ext):  # e.g. .zip, .tar.gz, etc.
                unpackable = True
                break

        if not unpackable:
            logger.info(
                f"File {downloaded.file_path} is not unpackable. Skipping unpack."
            )
            continue

        if empty_destination_before_unpack:
            logger.info(f"Emptying destination folder {folder} before unpacking.")
            deleted_files = []
            for item in folder.iterdir():
                if item.name == downloaded.file_path.name:
                    continue

                if item.as_posix() in [
                    new_file.file_path.as_posix()
                    for new_file in download_results
                    if new_file.success
                ]:
                    logger.info(
                        f"Skipping {item} as it is part of the current download results."
                    )
                    continue

                if item.is_file():
                    item.unlink()
                    deleted_files.append(item)
                elif item.is_dir():
                    shutil.rmtree(item)
                    deleted_files.append(item)

            logger.info(
                f"Deleted {len(deleted_files)} files/directories from {folder}."
            )
            logger.debug(f"Deleted files: {deleted_files}")

        logger.info(f"Unpacking {downloaded.file_path} to {folder}")

        shutil.unpack_archive(downloaded.file_path, extract_dir=folder)
        if delete_after_unpack:
            logger.info(f"Deleting {downloaded.file_path} after unpacking.")
            downloaded.file_path.unlink()

        unpacked_files.append(downloaded.file_path)

    logger.info(f"Unpacked {len(unpacked_files)} files.")

    return download_results, unpacked_files
