from pathlib import Path
from prefect_managedfiletransfer import RemoteAsset, TransferBlockType
from prefect_managedfiletransfer.RCloneConfigSavedInPrefect import (
    RCloneConfigSavedInPrefect,
)
from prefect_managedfiletransfer.RemoteConnectionType import RemoteConnectionType
from prefect_managedfiletransfer.delete_asset import delete_asset
from prefect_managedfiletransfer.password_utils import get_password_value
from prefect import task
from contextlib import nullcontext
import logging

logger = logging.getLogger(__name__)


@task(
    retries=2,
    retry_delay_seconds=60,
    timeout_seconds=60 * 30,
    task_run_name="delete-{remote_asset.path}",
)
async def delete_file_task(
    source_block: TransferBlockType,
    source_type: RemoteConnectionType,
    remote_asset: RemoteAsset,
    rclone_config: RCloneConfigSavedInPrefect | None = None,
) -> Path:
    """
    Task to delete a single file from a remote source (SFTP, RClone, or LocalFileSystem).

    Args:
        source_block (TransferBlockType): The block representing the source connection.
        source_type (RemoteConnectionType): The type of the source connection.
        remote_asset (RemoteAsset): The remote asset to delete.
        rclone_config (RCloneConfigSavedInPrefect | None): The RClone configuration to use for the deletion, if applicable.

    Returns:
        Path: The path of the deleted file.
    """

    logger.info(f"Start delete {remote_asset.path}")

    with (
        source_block.get_temp_key_file()
        if hasattr(source_block, "get_temp_key_file")
        else nullcontext()
    ) as temp_key_file:
        await delete_asset(
            file=remote_asset,
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
        )

    return remote_asset.path
