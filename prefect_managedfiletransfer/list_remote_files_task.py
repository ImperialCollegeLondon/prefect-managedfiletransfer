from datetime import datetime, timezone
from prefect_managedfiletransfer import TransferBlockType
from prefect_managedfiletransfer.RCloneConfigSavedInPrefect import (
    RCloneConfigSavedInPrefect,
)
from prefect_managedfiletransfer.RemoteConnectionType import RemoteConnectionType
from prefect_managedfiletransfer.PathUtil import PathUtil
from prefect_managedfiletransfer.FileMatcher import FileMatcher
from prefect_managedfiletransfer.RemoteAsset import RemoteAsset
from prefect_managedfiletransfer.list_remote_assets import list_remote_assets
from prefect_managedfiletransfer.password_utils import get_password_value


from prefect import task


from contextlib import nullcontext

import logging

logger = logging.getLogger(__name__)


@task(task_run_name="list_{matcher.source_folder}_{matcher.pattern_to_match}")
async def list_remote_files_task(
    source_block: TransferBlockType,
    source_type: RemoteConnectionType,
    matcher: FileMatcher,
    rclone_config: RCloneConfigSavedInPrefect | None = None,
    reference_date: datetime | None = None,
) -> list[RemoteAsset]:
    """
    Task to list remote files based on a matcher. Remote can be SFTP, RClone, or LocalFileSystem.

    Args:
        source_block (TransferBlockType): The block representing the source connection.
        source_type (RemoteConnectionType): The type of the source connection.
        matcher (FileMatcher): The matcher defining the pattern to match files.
        rclone_config (RCloneConfigSavedInPrefect | None): The RClone configuration to use for the remote connection, if applicable.
        reference_date (datetime | None): The reference date to use for filtering files. Defaults to None, which uses the current time.

    Returns:
        list[RemoteAsset]: A list of RemoteAsset objects that match the given pattern.
    """

    basepath_str = source_block.basepath if hasattr(source_block, "basepath") else None
    remote_source_path = PathUtil.resolve_path(
        source_type, basepath_str, matcher.source_folder
    )

    if reference_date is None:
        reference_date = datetime.now(timezone.utc)

    logger.debug(f"Listing remote files in {remote_source_path} with matcher {matcher}")

    files: list[RemoteAsset] = []
    with (
        source_block.get_temp_key_file()
        if hasattr(source_block, "get_temp_key_file")
        else nullcontext()
    ) as temp_key_file:
        found = await list_remote_assets(
            remote_folder=remote_source_path,
            pattern_to_match=matcher.pattern_to_match,
            remote_type=source_type,
            host=source_block.host if hasattr(source_block, "host") else None,
            port=source_block.port if hasattr(source_block, "port") else None,
            username=(
                source_block.username if hasattr(source_block, "username") else None
            ),
            password=(
                get_password_value(source_block.password)
                if hasattr(source_block, "password")
                else None
            ),
            private_key_path=(temp_key_file.get_path() if temp_key_file else None),
            rclone_config=rclone_config,
            minimum_age=matcher.minimum_age,
            maximum_age=matcher.maximum_age,
            sort=matcher.sort,
            skip=matcher.skip,
            take=matcher.take,
            reference_date=reference_date,
        )
        files.extend(found)

    logger.info(
        f"Found {len(files)} remote files in {remote_source_path} with matcher {matcher}"
    )

    return files
