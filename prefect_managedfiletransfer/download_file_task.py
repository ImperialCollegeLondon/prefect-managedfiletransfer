from datetime import datetime, timezone
from pathlib import Path
from prefect_managedfiletransfer import RemoteAsset, TransferBlockType
from prefect_managedfiletransfer.AssetDownloadResult import AssetDownloadResult
from prefect_managedfiletransfer.RCloneConfigSavedInPrefect import (
    RCloneConfigSavedInPrefect,
)
from prefect_managedfiletransfer.RemoteConnectionType import RemoteConnectionType
from prefect_managedfiletransfer.download_asset import download_asset
from prefect_managedfiletransfer.password_utils import get_password_value


from prefect import task


from contextlib import nullcontext
import logging

logger = logging.getLogger(__name__)


@task(
    retries=2,
    retry_delay_seconds=60,
    timeout_seconds=60 * 30,
    task_run_name="download-{remote_asset.path}",
)
async def download_file_task(
    source_block: TransferBlockType,
    source_type: RemoteConnectionType,
    remote_asset: RemoteAsset,
    target_file_path: Path,
    update_only_if_newer_mode: bool,
    overwrite: bool,
    mode: str,
    rclone_config: RCloneConfigSavedInPrefect | None,
    check_for_space: bool,
    check_for_space_overhead: int,
    reference_date: datetime | None = None,
) -> AssetDownloadResult:
    """
    Task to download a single file from a remote source (SFTP, RClone, or LocalFileSystem) to a local path
    Args:
        source_block (TransferBlockType): The block representing the source connection.
        source_type (RemoteConnectionType): The type of the source connection.
        remote_asset (RemoteAsset): The remote asset to download.
        target_file_path (Path): The path where the file should be downloaded.
        update_only_if_newer_mode (bool): If true, skip files that are newer on the destination.
        overwrite (bool): If true, overwrite the file if it exists.
        mode (str): The transfer mode to use (e.g., Copy, Move).
        rclone_config (RCloneConfigSavedInPrefect | None): The RClone configuration to use for the download, if applicable.
        check_for_space (bool): If true, check if there is enough space on the destination.
        check_for_space_overhead (int): The overhead space to consider when checking for space in bytes.
        reference_date (datetime | None): The reference date to use for checking file modification times. Defaults to None, which uses the current time.
    Returns:
        AssetDownloadResult: The result of the download operation, including success status and any error messages.
    """

    logger.info(f"Start download {remote_asset.path} to {target_file_path}")

    if not reference_date:
        reference_date = datetime.now(timezone.utc)

    with (
        source_block.get_temp_key_file()
        if hasattr(source_block, "get_temp_key_file")
        else nullcontext()
    ) as temp_key_file:
        download_result = await download_asset(
            file=remote_asset,
            destination_path=target_file_path,
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
            update_only_if_newer_mode=update_only_if_newer_mode,
            overwrite=overwrite,
            check_for_space=check_for_space,
            check_for_space_overhead=check_for_space_overhead,
            mode=mode,
            reference_date=reference_date,
        )
        if not download_result.success:
            logger.error(
                f"Failed to download {remote_asset.path}: {download_result.error}"
            )
            raise Exception(download_result.error)

        return download_result
