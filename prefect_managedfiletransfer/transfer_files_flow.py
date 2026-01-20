from datetime import datetime, timezone
from pathlib import Path
from prefect.runtime import flow_run
from prefect_managedfiletransfer.list_remote_files_task import list_remote_files_task
from prefect_managedfiletransfer.FileToFolderMapping import FileToFolderMapping
from prefect_managedfiletransfer.FileMatcher import FileMatcher
from prefect_managedfiletransfer.RCloneConfigSavedInPrefect import (
    RCloneConfigSavedInPrefect,
)
from prefect_managedfiletransfer.RCloneConfigFileBlock import RCloneConfigFileBlock
from prefect_managedfiletransfer.ServerWithBasicAuthBlock import (
    ServerWithBasicAuthBlock,
)
from prefect_managedfiletransfer.ServerWithPublicKeyAuthBlock import (
    ServerWithPublicKeyAuthBlock,
)
from prefect_managedfiletransfer.download_file_task import download_file_task
from prefect_managedfiletransfer.upload_file_task import upload_file_task
from prefect_managedfiletransfer.constants import CONSTANTS
from prefect_managedfiletransfer.RemoteConnectionType import RemoteConnectionType
from prefect_managedfiletransfer.PathUtil import PathUtil
from prefect_managedfiletransfer.RemoteAsset import RemoteAsset
from prefect_managedfiletransfer.TransferType import TransferType
from prefect_managedfiletransfer.block_utils import try_fetch_block
from prefect import State, flow
from prefect.filesystems import LocalFileSystem
from prefect.states import Completed
import logging


logger = logging.getLogger(__name__)


def _generate_flow_run_name() -> str:
    parameters = flow_run.parameters
    source = parameters["source_block_or_blockname"]
    dest = parameters["destination_block_or_blockname"]
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

    return f"{mode_str}-{source}-to-{dest}:{destination_folder}"


@flow(
    name=CONSTANTS.FLOW_NAMES.TRANSFER_FILES,
    log_prints=True,
    flow_run_name=_generate_flow_run_name,
    retries=2,
    retry_delay_seconds=60 * 20,  # retry every 20 minutes
    timeout_seconds=60 * 30,  # timeout after 30 minutes
)
async def transfer_files_flow(
    source_block_or_blockname: (
        ServerWithBasicAuthBlock
        | ServerWithPublicKeyAuthBlock
        | LocalFileSystem
        | RCloneConfigFileBlock
        | str
    ),
    destination_block_or_blockname: (
        ServerWithBasicAuthBlock
        | ServerWithPublicKeyAuthBlock
        | LocalFileSystem
        | RCloneConfigFileBlock
        | str
    ),
    source_file_matchers: list[FileMatcher] = [FileMatcher()],
    path_mapping: list[FileToFolderMapping] = [],
    destination_folder: Path = Path("."),
    update_only_if_newer_mode: bool = False,
    overwrite: bool = False,
    check_for_space: bool = True,
    check_for_space_overhead: int = 2 * 1024 * 1024 * 1024,  # 2GB overhead
    mode: TransferType = TransferType.Copy,
    reference_date: datetime | None = None,
) -> list[Path] | State:
    """
    Transfers files from a source to a destination based on the provided matchers and mapping.
    Args:
        source_block_or_blockname: The source block or block name to transfer files from.
        destination_block_or_blockname: The destination block or block name to transfer files to.
        source_file_matchers: List of file matcheing patterns to find and filter files in the source.
        path_mapping: List of file-to-folder mappings for transferring files.
        destination_folder: The path of the folder in destination_block where files will be transferred.
        update_only_if_newer_mode: If true, skip files that are newer on the destination.
        overwrite: If true, overwrite existing files in the destination.
        check_for_space: If true, check if there is enough space on the destination before transferring.
        check_for_space_overhead: Amount of extra space to reserve on the destination (in bytes).
        mode: Copy or Move transfer mode.
        reference_date: defaults to now() in UTC - used to filter files based on modification time, and for pattern replacement in file names
    Returns:
        A list of the Paths of transferred files.
    """
    if not source_file_matchers:
        raise ValueError("No source file matchers provided")

    if reference_date is None:
        reference_date = datetime.now(timezone.utc)

    if source_block_or_blockname is None:
        raise ValueError("Source block or blockname is missing")

    if destination_block_or_blockname is None:
        raise ValueError("Destination block or blockname is missing")

    source_block: (
        ServerWithBasicAuthBlock
        | ServerWithPublicKeyAuthBlock
        | LocalFileSystem
        | RCloneConfigFileBlock
    )
    if isinstance(source_block_or_blockname, str):
        source_block = await try_fetch_block(source_block_or_blockname)
    else:
        source_block = source_block_or_blockname

    destination_block: (
        ServerWithBasicAuthBlock
        | ServerWithPublicKeyAuthBlock
        | LocalFileSystem
        | RCloneConfigFileBlock
    )
    if isinstance(destination_block_or_blockname, str):
        destination_block = await try_fetch_block(destination_block_or_blockname)
    else:
        destination_block = destination_block_or_blockname

    # cannot both be local file systems
    if not isinstance(source_block, LocalFileSystem) and not isinstance(
        destination_block, LocalFileSystem
    ):
        raise ValueError(
            "Cannot transfer files between two remote file systems. One must be local."
        )

    source_type = map_block_to_remote_type(source_block)
    destination_type = map_block_to_remote_type(destination_block)
    rclone_source_config = (
        RCloneConfigSavedInPrefect(source_block)
        if isinstance(source_block, RCloneConfigFileBlock)
        else None
    )
    rclone_destination_config = (
        RCloneConfigSavedInPrefect(destination_block)
        if isinstance(destination_block, RCloneConfigFileBlock)
        else None
    )

    source_files: list[RemoteAsset] = []
    for matcher in source_file_matchers:
        files = await list_remote_files_task(
            source_block,
            source_type,
            matcher,
            rclone_source_config,
            reference_date,
        )
        source_files.extend(files)

    basepath_str = (
        destination_block.basepath if hasattr(destination_block, "basepath") else None
    )

    resolved_destination_with_basepath = PathUtil.resolve_path(
        destination_type, basepath_str, destination_folder
    )

    source_destination_pairs = FileToFolderMapping.apply_mappings(
        path_mapping, source_files, resolved_destination_with_basepath
    )

    transferred = []
    for remote_asset, target_file_path in source_destination_pairs:
        if destination_type == RemoteConnectionType.LOCAL:
            downloaded_file = await download_file_task(
                source_block,
                source_type,
                remote_asset,
                target_file_path,
                update_only_if_newer_mode,
                overwrite,
                mode,
                rclone_source_config,
                check_for_space,
                check_for_space_overhead,
                reference_date,
            )
            transferred.append(downloaded_file)
        else:
            upload_result = await upload_file_task(
                remote_asset,
                destination_block,
                destination_type,
                target_file_path,
                update_only_if_newer_mode,
                overwrite,
                mode,
                rclone_config=rclone_destination_config,
                check_for_space=check_for_space,
                check_for_space_overhead=check_for_space_overhead,
                reference_date=reference_date,
            )
            transferred.append(upload_result)

    logger.info(f"Transfer completed. {len(transferred)} files processed")

    if len(transferred) == 0:
        return Completed(
            message="No files to transfer",
            name=CONSTANTS.SKIPPED_STATE_NAME,
        )

    return transferred


def map_block_to_remote_type(source_block):
    source_type = RemoteConnectionType.LOCAL
    if isinstance(source_block, ServerWithBasicAuthBlock) or isinstance(
        source_block, ServerWithPublicKeyAuthBlock
    ):
        source_type = RemoteConnectionType.SFTP
    elif isinstance(source_block, RCloneConfigFileBlock):
        source_type = RemoteConnectionType.RCLONE
    return source_type


# quick way to just run/test this flow without deployment. start server in one terminal and serve flow in another
# $ prefect server start
# $ PREFECT_LOGGING_EXTRA_LOGGERS=prefect_managedfiletransfer PREFECT_LOGGING_LEVEL=DEBUG python transfer_files_flow.py

if __name__ == "__main__":
    transfer_files_flow.serve(
        name=CONSTANTS.DEPLOYMENT_NAMES.TRANSFER_FILES, tags=["dev"]
    )
