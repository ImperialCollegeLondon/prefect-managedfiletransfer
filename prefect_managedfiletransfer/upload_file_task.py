from datetime import datetime
from prefect_managedfiletransfer import RemoteConnectionType, TransferType
from prefect_managedfiletransfer.RCloneConfigFileBlock import RCloneConfigFileBlock
from prefect_managedfiletransfer.RemoteAsset import RemoteAsset
from prefect_managedfiletransfer.ServerWithBasicAuthBlock import (
    ServerWithBasicAuthBlock,
)
from prefect_managedfiletransfer.ServerWithPublicKeyAuthBlock import (
    ServerWithPublicKeyAuthBlock,
)
from prefect_managedfiletransfer.upload_asset import upload_asset
from prefect_managedfiletransfer.password_utils import get_password_value
from prefect import task
from prefect.filesystems import LocalFileSystem
import logging
from contextlib import nullcontext
from pathlib import Path

logger = logging.getLogger(__name__)


@task(
    retries=2,
    retry_delay_seconds=60,
    timeout_seconds=60 * 30,
    task_run_name="upload-{target_file_path}",
)
async def upload_file_task(
    source_remote_asset: RemoteAsset,
    destination_block: (
        ServerWithBasicAuthBlock
        | ServerWithPublicKeyAuthBlock
        | LocalFileSystem
        | RCloneConfigFileBlock
    ),
    destination_type: RemoteConnectionType,
    target_file_path: Path,
    update_only_if_newer_mode: bool,
    overwrite: bool,
    mode: TransferType,
    rclone_config: RCloneConfigFileBlock,
    check_for_space: bool,
    check_for_space_overhead: int,
    reference_date: datetime,
) -> Path:
    """
    Task to upload a single file to a remote destination (local/SFTP/RClone remote).

    Args:
        source_remote_asset (RemoteAsset): The remote asset to upload.
        destination_block (ServerWithBasicAuthBlock | ServerWithPublicKeyAuthBlock | LocalFileSystem | RCloneConfigFileBlock): The block representing the destination.
        destination_type (RemoteConnectionType): The type of the destination connection.
        target_file_path (Path): The path where the file should be uploaded.
        update_only_if_newer_mode (bool): If true, skip files that are newer on the destination.
        overwrite (bool): If true, overwrite the file if it exists.
        mode (TransferType): The transfer mode to use (e.g., Copy, Move).
        rclone_config (RCloneConfigFileBlock): The RClone configuration block to use for the upload.
        check_for_space (bool): If true, check if there is enough space on the destination.
        check_for_space_overhead (int): The overhead space to consider when checking for space in bytes.
        reference_date (datetime): now() in UTC. The reference date to use for checking file modification times. Used in testing.
    Returns:
        Path: The path to the uploaded file.
    """

    logger.info(f"Start upload {source_remote_asset.path} to {target_file_path}")

    with (
        destination_block.get_temp_key_file()
        if hasattr(destination_block, "get_temp_key_file")
        else nullcontext()
    ) as temp_key_file:
        upload_result = await upload_asset(
            source_folder=source_remote_asset.path.parent,
            pattern_to_upload=source_remote_asset.path.name,
            destination_file=target_file_path,
            destination_type=destination_type,
            host=(
                destination_block.host if hasattr(destination_block, "host") else None
            ),
            port=(
                destination_block.port if hasattr(destination_block, "port") else None
            ),
            username=(
                destination_block.username
                if hasattr(destination_block, "username")
                else None
            ),
            password=(
                get_password_value(destination_block.password)
                if hasattr(destination_block, "password")
                else None
            ),
            private_key_path=(temp_key_file.get_path() if temp_key_file else None),
            rclone_config=rclone_config,
            update_only_if_newer_mode=update_only_if_newer_mode,
            overwrite=overwrite,
            mode=mode,
            check_for_space=check_for_space,
            check_for_space_overhead=check_for_space_overhead,
            reference_datetime=reference_date,
        )
        if upload_result != 0:
            logger.error(
                f"Failed to upload {source_remote_asset.path} to {target_file_path}. Exit code {upload_result}"
            )
            raise Exception("Upload failed")

        return target_file_path
