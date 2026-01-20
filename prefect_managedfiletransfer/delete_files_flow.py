from datetime import datetime, timezone
from pathlib import Path
from prefect.runtime import flow_run
from prefect_managedfiletransfer.list_remote_files_task import list_remote_files_task
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
from prefect_managedfiletransfer.delete_file_task import delete_file_task
from prefect_managedfiletransfer.constants import CONSTANTS
from prefect_managedfiletransfer.RemoteConnectionType import RemoteConnectionType
from prefect_managedfiletransfer.RemoteAsset import RemoteAsset
from prefect_managedfiletransfer.block_utils import try_fetch_block
from prefect import State, flow
from prefect.filesystems import LocalFileSystem
import logging
from prefect.states import Completed

logger = logging.getLogger(__name__)


def _generate_flow_run_name() -> str:
    parameters = flow_run.parameters
    source = parameters["source_block_or_blockname"]
    source_file_matchers: list[FileMatcher] = parameters["source_file_matchers"]

    if hasattr(source, "host"):
        source = f"{source.host}:{source.port}"
    else:
        source = str(source)

    if len(source_file_matchers) == 1:
        source += f":{source_file_matchers[0].source_folder}/{source_file_matchers[0].pattern_to_match}"

    return f"delete-{source}"


@flow(
    name=CONSTANTS.FLOW_NAMES.DELETE_FILES,
    log_prints=True,
    flow_run_name=_generate_flow_run_name,
    retries=2,
    retry_delay_seconds=60 * 20,  # retry every 20 minutes
    timeout_seconds=60 * 30,  # timeout after 30 minutes
)
async def delete_files_flow(
    source_block_or_blockname: (
        ServerWithBasicAuthBlock
        | ServerWithPublicKeyAuthBlock
        | LocalFileSystem
        | RCloneConfigFileBlock
        | str
    ),
    source_file_matchers: list[FileMatcher] = [FileMatcher()],
    reference_date: datetime | None = None,
) -> list[Path] | State:
    """
    Deletes files from a source based on the provided matchers.

    Args:
        source_block_or_blockname: The source block or block name to delete files from.
        source_file_matchers: List of file matching patterns to find and filter files in the source.
        reference_date: defaults to now() in UTC - used to filter files based on modification time, and for pattern replacement in file names

    Returns:
        A list of the Paths of deleted files.
    """
    if not source_file_matchers:
        raise ValueError("No source file matchers provided")

    if reference_date is None:
        reference_date = datetime.now(timezone.utc)

    if source_block_or_blockname is None:
        raise ValueError("Source block or blockname is missing")

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

    source_type = map_block_to_remote_type(source_block)
    rclone_source_config = (
        RCloneConfigSavedInPrefect(source_block)
        if isinstance(source_block, RCloneConfigFileBlock)
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

    deleted = []
    for remote_asset in source_files:
        deleted_file = await delete_file_task(
            source_block,
            source_type,
            remote_asset,
            rclone_source_config,
        )
        deleted.append(deleted_file)

    logger.info(f"Delete completed. {len(deleted)} files removed")

    if len(deleted) == 0:
        return Completed(
            message="No files to delete",
            name=CONSTANTS.SKIPPED_STATE_NAME,
        )

    return deleted


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
# $ PREFECT_LOGGING_EXTRA_LOGGERS=prefect_managedfiletransfer PREFECT_LOGGING_LEVEL=DEBUG python delete_files_flow.py

if __name__ == "__main__":
    delete_files_flow.serve(name=CONSTANTS.DEPLOYMENT_NAMES.DELETE_FILES, tags=["dev"])
