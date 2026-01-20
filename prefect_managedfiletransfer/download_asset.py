import logging
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil

from prefect_managedfiletransfer.RemoteAsset import RemoteAsset
from prefect_managedfiletransfer.RCloneCommandBuilder import RCloneCommandBuilder
from prefect_managedfiletransfer.TransferType import TransferType
from prefect_managedfiletransfer.ensure_space import ensure_space
from prefect_managedfiletransfer.sftp_utils import connect_to_sftp_remote
from prefect_managedfiletransfer.delete_asset import delete_asset

from prefect_managedfiletransfer.AssetDownloadResult import AssetDownloadResult
from prefect_managedfiletransfer.invoke_rclone import invoke_rclone
from prefect_managedfiletransfer.RemoteConnectionType import RemoteConnectionType
from prefect_managedfiletransfer.RCloneConfig import RCloneConfig

logger = logging.getLogger(__name__)


async def download_asset(
    file: RemoteAsset,
    destination_path: Path,
    remote_type: RemoteConnectionType,
    host: str | None = None,
    port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    private_key_path: (Path | None) = None,  # for SFTP with public/private key auth
    rclone_config_file: Path | None = None,
    rclone_config: RCloneConfig | None = None,
    # if true skip files that are newer on the destination
    update_only_if_newer_mode: bool = False,
    overwrite: bool = False,
    # if True, check if there is enough space on the remote destination before uploading. NOT RCLONE
    check_for_space: bool = False,
    # space overhead in bytes to ensure available on the remote destination before uploading. NOT RCLONE
    check_for_space_overhead: int = 0,
    mode: TransferType = TransferType.Copy,
    reference_date: datetime = datetime.now(
        timezone.utc
    ),  # used in generating timestamps
) -> AssetDownloadResult:
    """
    Download file from the remote and place it at local destination path
    if destination file already exists, it will be overwritten if overwrite or update modes are used
    if destintaion is a folder, the file will be placed in that folder with the same name as the remote file
    """

    logger.debug(
        f"Downloading file {file.path} from {remote_type.name} remote to {destination_path}"
    )

    if rclone_config_file is not None and rclone_config is not None:
        raise ValueError(
            "rclone_config_file and rclone_config_contents cannot be used at the same time"
        )

    if rclone_config_file is not None and not rclone_config_file.exists():
        logger.critical(f"rclone config file {rclone_config_file} does not exist")
        raise FileNotFoundError(
            f"rclone config file {rclone_config_file} does not exist"
        )

    if file is None or file.path is None:
        logger.critical("File to download cannot be None or empty")
        raise ValueError("File to download cannot be None or empty")

    if not destination_path:
        logger.critical("Destination path cannot be None or empty")
        raise ValueError("Destination path cannot be None or empty")

    if not isinstance(destination_path, Path):
        logger.critical(
            f"Destination path must be a Path object, got {type(destination_path)}"
        )
        raise TypeError(
            f"Destination path must be a Path object, got {type(destination_path)}"
        )

    if destination_path.is_dir() or str(destination_path.as_posix()).endswith("/"):
        # if the destination is a directory, we need to create the full path with the file name
        destination_path = destination_path / file.path.name

    destination_folder = destination_path.parent
    if not destination_folder.exists():
        logger.debug(f"Creating destination folder {destination_folder}")
        try:
            destination_folder.mkdir(exist_ok=True, parents=True)
        except Exception as e:
            msg = f"Failed to create destination folder {destination_folder}: {e}"
            logger.error(msg)
            return AssetDownloadResult(
                success=False,
                file_path=None,
                error=msg,
            )

    if destination_path.exists() and update_only_if_newer_mode:
        file_stat = destination_path.stat()
        dest_last_modified = datetime.fromtimestamp(file_stat.st_mtime, tz=timezone.utc)
        if file.last_modified <= dest_last_modified:
            logger.info(
                f"Skipping download of {file.path} to {destination_path} as it is not newer than the destination file"
            )
            return AssetDownloadResult(
                success=True,
                file_path=destination_path,
                download_skipped=True,
                last_modified=dest_last_modified,
            )

    if destination_path.exists() and not overwrite and not update_only_if_newer_mode:
        msg = f"Destination file {destination_path} already exists and overwrite is False, download aborted"
        logger.error(msg)
        return AssetDownloadResult(
            success=False,
            file_path=None,
            error=msg,
        )

    destination_temp_file = destination_path.with_suffix(
        ".tmp" + reference_date.strftime("%Y%m%d%H%M%S")
    )

    if destination_temp_file.exists():
        # we assume that a file with "temp" suffix and the timestamp in it must be safe to delete
        logger.info(
            f"Temporary file {destination_temp_file} already exists, removing it"
        )
        destination_temp_file.unlink()

    if check_for_space:
        available_space = shutil.disk_usage(destination_folder).free
        ensure_space(
            file.size,
            available_space,
            check_for_space_overhead,
            destination_folder,
        )
    else:
        logger.debug(f"Skipping local disk space check for {destination_folder}")

    logger.info(f"Copying {file.path} to temporary file {destination_temp_file}")

    result = None
    match remote_type:
        case RemoteConnectionType.LOCAL:
            if not file.path.exists():
                logger.info(f"Remote (local!) file {file.path} does not exist")
                return AssetDownloadResult(
                    success=False,
                    file_path=None,
                    error=f"Remote file {file.path} does not exist",
                )

            shutil.copy2(file.path, destination_temp_file)

            result = check_and_move_downloaded_temp_file(
                destination_temp_file, destination_path, file, overwrite
            )
            if result.success and mode == TransferType.Move:
                await delete_asset(
                    file=file,
                    remote_type=RemoteConnectionType.LOCAL,
                )

        case RemoteConnectionType.SFTP:
            transport = None
            sftp = None
            try:
                transport, sftp = connect_to_sftp_remote(
                    host, port, username, password, private_key_path
                )

                parent_folder = str(file.path.parent)
                logger.debug(f"SFTP chdir '{parent_folder}'")
                try:
                    sftp.chdir(parent_folder)
                except FileNotFoundError:
                    message = f"Remote folder {parent_folder} does not exist"
                    logger.error(message)
                    return AssetDownloadResult(
                        success=False, file_path=None, error=message
                    )

                logger.info(
                    f"Downloading remote file {file.path.name} to temporary file {destination_temp_file}"
                )
                try:
                    sftp.get(file.path.name, destination_temp_file.as_posix())
                except FileNotFoundError:
                    message = f"Remote file {file.path.name} does not exist"
                    logger.error(message)
                    return AssetDownloadResult(
                        success=False, file_path=None, error=message
                    )

                result = check_and_move_downloaded_temp_file(
                    destination_temp_file, destination_path, file, overwrite
                )

                if result.success and mode == TransferType.Move:
                    # We could pass this on the the shared code for delete - but that has overheads of connecting again
                    # await delete_asset(
                    #     file=file,
                    #     remote_type=RemoteConnectionType.SFTP,
                    #     host=host,
                    #     port=port,
                    #     username=username,
                    #     password=password,
                    #     private_key_path=private_key_path,
                    # )
                    logger.info(f"Deleting remote file {file.path.name} after move")
                    sftp.remove(file.path.name)
            finally:
                if sftp is not None:
                    sftp.close()
                if transport is not None:
                    transport.close()

        case RemoteConnectionType.RCLONE:
            rclone_command = (
                RCloneCommandBuilder(rclone_config_file, rclone_config)
                .downloadTo(file.path, destination_path, update_only_if_newer_mode)
                .build()
            )

            return_code, config_after, captured_output, exception = invoke_rclone(
                rclone_command,
                config_file_contents=(
                    rclone_config.get_config() if rclone_config else None
                ),
                logger=logger,
            )

            if return_code == 0 and rclone_config is not None and config_after:
                logger.info(
                    f"Updating rclone config for remote {rclone_config.remote_name}"
                )
                await rclone_config.update_config(config_after)

            if type(exception) is FileNotFoundError:
                return AssetDownloadResult(
                    success=False,
                    file_path=None,
                    error=f"Remote file {file.path} does not exist",
                )
            elif return_code != 0:
                message = f"Failed to download file {file.path} with rclone, return code {return_code}"
                return AssetDownloadResult(success=False, file_path=None, error=message)

            result = check_and_move_downloaded_temp_file(
                None, destination_path, file, overwrite
            )
            if result.success and mode == TransferType.Move:
                await delete_asset(
                    file=file,
                    remote_type=RemoteConnectionType.RCLONE,
                    rclone_config_file=rclone_config_file,
                    rclone_config=rclone_config,
                )

        case _:
            logger.critical(f"Unknown remote type {remote_type}")
            raise ValueError(f"Unknown remote type {remote_type}")

    return result


def check_and_move_downloaded_temp_file(
    destination_temp_file: Path | None,
    destination_path: Path,
    file: RemoteAsset,
    overwrite: bool = False,
) -> AssetDownloadResult:
    """Check the downloaded temporary file if ok and if so and move it to the final path."""

    if destination_path is None or len(destination_path.as_posix()) == 0:
        raise ValueError("Destination path cannot be None or empty")

    if not file or file.path is None:
        raise ValueError("File to download cannot be None or empty")

    if destination_temp_file is not None:
        if not destination_temp_file.exists():
            msg = (
                f"Temporary file {destination_temp_file} does not exist after download"
            )
            logger.error(msg)
            return AssetDownloadResult(success=False, file_path=None, error=msg)

        destination_size = destination_temp_file.stat().st_size
        if destination_size == 0:
            msg = (
                f"Temporary file {destination_temp_file} is zero bytes, download failed"
            )
            logger.error(msg)
            destination_temp_file.unlink()
            return AssetDownloadResult(success=False, file_path=None, error=msg)

        if destination_size != file.size:
            msg = f"Temporary file {destination_temp_file} size {destination_size} does not match expected size {file.size}, download failed"
            logger.error(msg)
            destination_temp_file.unlink()
            return AssetDownloadResult(success=False, file_path=None, error=msg)

        if destination_path.exists() and overwrite:
            logger.info(f"Overwriting existing file {destination_path}")
            destination_path.unlink()

        # if it still exists now something has gone really wrong as we have already checked wecan overwrite/update and have tried to delete it
        if destination_path.exists():
            # fail - this should not happen unless something else has written while we are downloading or the delete failed
            msg = f"Destination file {destination_path} already exists and unable to overwrite, rename aborted after download"
            logger.error(msg)
            return AssetDownloadResult(
                success=False,
                file_path=None,
                error=msg,
            )

        shutil.move(destination_temp_file, destination_path)

    # set the modified time to the original file's modified time
    if file.last_modified:
        file_mtime = file.last_modified.timestamp()
        os.utime(destination_path, (file_mtime, file_mtime))

    # check if the move was successful
    if not destination_path.exists():
        msg = f"Failed to move temporary file {destination_temp_file} to final destination {destination_path}"
        logger.error(msg)
        return AssetDownloadResult(
            success=False,
            file_path=None,
            error=msg,
        )

    if not destination_path.is_file():
        msg = f"Final destination {destination_path} is not a file after move, download failed"
        logger.error(msg)
        return AssetDownloadResult(
            success=False,
            file_path=None,
            error=msg,
        )

    destination_size = destination_path.stat().st_size
    if destination_size == 0:
        msg = f"Final destination {destination_path} is zero bytes after move, download failed"
        logger.error(msg)
        destination_path.unlink()
        return AssetDownloadResult(
            success=False,
            file_path=None,
            error=msg,
        )

    if destination_size != file.size:
        msg = f"Final destination {destination_path} size {destination_size} does not match expected size {file.size}, download failed"
        logger.error(msg)
        destination_path.unlink()
        return AssetDownloadResult(
            success=False,
            file_path=None,
            error=msg,
        )

    file_mtime = destination_path.stat().st_mtime
    last_modified = datetime.fromtimestamp(file_mtime, tz=timezone.utc)

    if destination_temp_file is not None:
        logger.debug(
            f"Finished move of temp file {destination_temp_file} to final path {destination_path} and update modified time"
        )

    logger.info(
        f"Downloaded file {file.path} to {destination_path.absolute().as_posix()} ({destination_size} bytes, modified {last_modified})"
    )

    return AssetDownloadResult(
        success=True,
        file_path=destination_path,
        last_modified=last_modified,
        size=destination_size,
    )
