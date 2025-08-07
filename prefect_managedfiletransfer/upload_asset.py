import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


from prefect_managedfiletransfer.TransferType import TransferType
from prefect_managedfiletransfer.RCloneCommandBuilder import RCloneCommandBuilder
from prefect_managedfiletransfer.ensure_space import ensure_space
from prefect_managedfiletransfer.sftp_utils import (
    connect_to_sftp_remote,
    connect_to_sftp_remote_using_ssh,
    try_get_remote_disk_space,
)
from prefect_managedfiletransfer.list_remote_assets import list_remote_assets


from prefect_managedfiletransfer.invoke_rclone import invoke_rclone
from prefect_managedfiletransfer.RemoteConnectionType import RemoteConnectionType
from prefect_managedfiletransfer.RCloneConfig import RCloneConfig

logger = logging.getLogger(__name__)


async def upload_asset(
    source_folder: Path,
    pattern_to_upload: str,
    destination_file: Path,
    destination_type: RemoteConnectionType,
    host: str | None = None,
    port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    private_key_path: (Path | None) = None,  # for SFTP with public/private key auth
    # if true skip files that are newer on the destination
    update_only_if_newer_mode: bool = False,
    overwrite: bool = False,
    mode: TransferType = TransferType.Copy,
    rclone_config_file: Path | None = None,
    rclone_config: RCloneConfig | None = None,
    # if True, check if there is enough space on the remote destination before uploading. NOT RCLONE
    check_for_space: bool = False,
    # space overhead in bytes to ensure available on the remote destination before uploading. NOT RCLONE
    check_for_space_overhead: int = 0,
    logger: logging.Logger = logger,
    reference_datetime: datetime = datetime.now(
        timezone.utc
    ),  # used in generating timestamps
) -> int:
    """
    Upload (copy) a single file matching a pattern to the destination, e.g. upload an image to the MAG Orbiter updates website.
    Takes the latest file if multiple are matched. Matches based on pathlim.match().
    If pattern contains a % then pythons datetime.now().strftime() is applied to the pattern e.g. "%Y-%m-%d.png matches file with todays date
    """

    logger.debug(f"Finding file matching {pattern_to_upload} in {source_folder}")

    # get all files in source_folder
    files: list[Path] = []

    # if pattern contains a %
    if "%" in pattern_to_upload:
        updated = reference_datetime.strftime(pattern_to_upload)
        logger.info(
            f"Pattern contains a %, replacing {pattern_to_upload} with {updated}"
        )
        pattern_to_upload = updated

    # list all files in the share
    for file in source_folder.iterdir():
        if file.is_file():
            if file.match(pattern_to_upload):
                files.append(file)

    # get the most recently modified matching file
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    if len(files) == 0:
        logger.critical(
            f"No files matching {pattern_to_upload} found in {source_folder}"
        )
        raise FileNotFoundError(
            f"No files matching {pattern_to_upload} found in {source_folder}"
        )
    elif len(files) == 1:
        logger.info(f"Found 1 matching file. {files[0].absolute().as_posix()}")
    else:
        logger.info(
            f"Found {len(files)} matching files. Using the most recent one: {files[0].absolute().as_posix()}"
        )

    source_file_path = files[0].absolute()
    source_file = source_file_path.as_posix()
    # Check source_file and destination_file have same size
    source_file_stats = source_file_path.stat()
    source_size = source_file_stats.st_size
    source_mtime = source_file_stats.st_mtime

    destination_size = 0
    upload_completed = False
    upload_skipped = False

    match destination_type:
        case RemoteConnectionType.LOCAL:
            # if destination folder does not exists create it
            destination_folder = destination_file.parent
            if not destination_folder.exists():
                logger.debug(f"Creating destination folder {destination_folder}")
                destination_folder.mkdir(exist_ok=True, parents=True)

            if (
                destination_file.exists()
                and not overwrite
                and not update_only_if_newer_mode
            ):
                RaiseFileAlreadyExists(destination_file)

            do_upload = True
            if destination_file.exists() and update_only_if_newer_mode:
                destination_mtime = destination_file.stat().st_mtime

                if source_mtime <= destination_mtime:
                    do_upload = False
                    upload_skipped = True

            if do_upload and check_for_space:
                available_space = shutil.disk_usage(destination_folder).free
                ensure_space(
                    source_size,
                    available_space,
                    check_for_space_overhead,
                    destination_folder,
                )
            else:
                logger.debug(
                    f"Skipping local disk space check for {destination_folder}"
                )

            if do_upload:
                logger.info(f"Copying {source_file} to {destination_file.absolute()}")

                shutil.copy2(source_file, destination_file)
                destination_size = destination_file.stat().st_size

                # set the modified time to the original file's modified time
                if source_mtime:
                    os.utime(destination_file, (source_mtime, source_mtime))
                upload_completed = True

        case RemoteConnectionType.SFTP:
            transport_or_ssh = None
            sftp = None
            try:
                if check_for_space:
                    transport_or_ssh, sftp = connect_to_sftp_remote_using_ssh(
                        host, port, username, password, private_key_path
                    )
                else:
                    transport_or_ssh, sftp = connect_to_sftp_remote(
                        host, port, username, password, private_key_path
                    )

                remote_file = destination_file.name

                destination_folder_str = str(destination_file.parent)

                logger.debug(f"SFTP chdir '{destination_folder_str}'")
                # ensure the destination folder exists
                try:
                    sftp.chdir(destination_folder_str)
                except FileNotFoundError:
                    logger.info(f"Creating destination folder {destination_folder_str}")
                    sftp.mkdir(destination_folder_str)
                    sftp.chdir(destination_folder_str)

                do_upload = True

                # Check if the file already exists and is newer
                if update_only_if_newer_mode:
                    try:
                        logger.info(
                            f"Checking if remote file {remote_file} was modified after {source_mtime}"
                        )
                        remote_file_info = sftp.stat(remote_file)
                        remote_mtime = remote_file_info.st_mtime

                        logger.debug(
                            f"Remote file {remote_file} last modified at {remote_mtime}"
                        )

                        if remote_mtime and source_mtime <= remote_mtime:
                            do_upload = False
                            upload_skipped = True
                    except FileNotFoundError:
                        logger.debug(f"Remote file {remote_file} does not exist")
                elif not overwrite:
                    try:
                        logger.debug(
                            f"Checking if remote file {remote_file} exists - overwrite is disabled"
                        )
                        sftp.stat(remote_file)
                        do_upload = False
                        RaiseFileAlreadyExists(remote_file)
                    except FileNotFoundError:
                        logger.debug(
                            f"Remote file {remote_file} does not exist, proceeding with upload"
                        )

                if do_upload and check_for_space:
                    available_space = try_get_remote_disk_space(
                        ssh_client=transport_or_ssh,
                        path=destination_folder_str,
                    )
                    ensure_space(
                        source_size,
                        available_space,
                        check_for_space_overhead,
                        destination_folder_str,
                    )
                else:
                    logger.debug(
                        f"Skipping sftp disk space check for {destination_folder_str}"
                    )

                if do_upload:
                    logger.info(
                        f"Uploading local '{source_file}' to '{destination_folder_str}' as '{remote_file}'"
                    )
                    sftp.put(localpath=source_file, remotepath=remote_file)

                    # try and set the modified time to the original file's modified time
                    if source_mtime:
                        logger.debug(
                            f"Setting remote file {remote_file} modified time to {source_mtime}"
                        )
                        sftp.utime(remote_file, (source_mtime, source_mtime))

                    remote_file_info = sftp.stat(remote_file)
                    upload_completed = True

                    if remote_file_info.st_size is None:
                        logger.warning(
                            f"Failed to get size of remote file {remote_file} - probably size is not supported by this server?"
                        )
                        destination_size = source_size
                    else:
                        destination_size = remote_file_info.st_size

            finally:
                if sftp is not None:
                    sftp.close()
                if transport_or_ssh is not None:
                    transport_or_ssh.close()

        case RemoteConnectionType.RCLONE:
            if check_for_space:
                raise NotImplementedError(
                    "RClone does not support checking for space before upload"
                )

            if not overwrite and not update_only_if_newer_mode:
                files_that_will_be_overwritten = await list_remote_assets(
                    remote_folder=destination_file.parent,
                    pattern_to_match=destination_file.name,
                    remote_type=destination_type,
                    rclone_config_file=rclone_config_file,
                    rclone_config=rclone_config,
                    reference_date=reference_datetime,
                )
                if len(files_that_will_be_overwritten) > 0:
                    RaiseFileAlreadyExists(destination_file)

            rclone_command = (
                RCloneCommandBuilder(rclone_config_file, rclone_config)
                .uploadTo(source_file, destination_file, update_only_if_newer_mode)
                .build()
            )

            return_code, config_after, output, exception = invoke_rclone(
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

            if return_code == 0:
                upload_completed = True

            # skip the destination file size check - rclone is smart enough to make sure it arrived ok
            destination_size = source_size

        case _:
            logger.critical(f"Unknown destination type {destination_type}")
            raise ValueError(f"Unknown destination type {destination_type}")

    if upload_completed:
        if source_size != destination_size:
            logger.error(
                f"Source file size {source_size} and destination file size {destination_size} do not match"
            )
            raise RuntimeError(
                f"Source file size {source_size} and destination file size {destination_size} do not match"
            )
        elif upload_completed and (source_size == 0) and (destination_size == 0):
            logger.warning(
                f"Source file size {source_size} and destination file size {destination_size} are both zero"
            )

        if mode == TransferType.Move:
            logger.debug(f"Deleting original file {source_file} after move")
            Path(source_file).unlink(missing_ok=True)
            logger.info(f"Deleted original file {source_file} after move")
    elif upload_skipped:
        logger.info(
            f"Upload skipped for {source_file} to {destination_file} as it is not newer than the destination file"
        )
        return 0
    else:
        logger.info(f"Did not upload {source_file} to {destination_file}")
        return 2

    return 0


def RaiseFileAlreadyExists(destination_file):
    msg = f"Destination file {destination_file} already exists and overwrite/update-if-newer both disabled, upload aborted"
    logger.error(msg)
    raise FileExistsError(msg)
