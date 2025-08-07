import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
import fnmatch

from prefect_managedfiletransfer.RCloneCommandBuilder import RCloneCommandBuilder
from prefect_managedfiletransfer.RemoteAsset import RemoteAsset
from prefect_managedfiletransfer.SortFilesBy import SortFilesBy
from prefect_managedfiletransfer.sftp_utils import connect_to_sftp_remote
from prefect_managedfiletransfer.time_util import convert_to_seconds

from prefect_managedfiletransfer.invoke_rclone import invoke_rclone
from prefect_managedfiletransfer.RemoteConnectionType import RemoteConnectionType
from prefect_managedfiletransfer.RCloneConfig import RCloneConfig

logger = logging.getLogger(__name__)


async def list_remote_assets(
    remote_folder: Path,
    pattern_to_match: str,
    remote_type: RemoteConnectionType,
    host: str | None = None,
    port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    private_key_path: (Path | None) = None,  # for SFTP with public/private key auth
    rclone_config_file: Path | None = None,
    rclone_config: RCloneConfig | None = None,
    # Only transfer files newer than this in s or suffix s|m|h|d|w|month|year (default off)
    minimum_age: str | int | timedelta | None = None,
    # Only transfer files younger than this in s or suffix s|m|h|d|w|month|year (default off)
    maximum_age: str | int | timedelta | None = None,
    take: int | None = None,  # how many to take, None for all
    skip: int = 0,  # how many to skip, default is 0
    sort: SortFilesBy = SortFilesBy.PATH_ASC,
    reference_date: datetime = datetime.now(timezone.utc),
) -> list[RemoteAsset]:
    """
    Get a list of files matching a pattern in a remote destination,
    If pattern contains a % then pythons datetime.now().strftime() is applied to the pattern e.g. "%Y-%m-%d.png matches file with todays date
    """

    logger.debug(
        f"Finding files matching {pattern_to_match} in {remote_folder} of type {remote_type.name}"
    )

    # make sure reference date is in UTC but without time zone info from UI
    if reference_date.tzinfo is not None:
        reference_date = reference_date.astimezone(timezone.utc).replace(tzinfo=None)

    if rclone_config_file is not None and rclone_config is not None:
        raise ValueError(
            "rclone_config_file and rclone_config_contents cannot be used at the same time"
        )

    if rclone_config_file is not None and not rclone_config_file.exists():
        logger.critical(f"rclone config file {rclone_config_file} does not exist")
        raise FileNotFoundError(
            f"rclone config file {rclone_config_file} does not exist"
        )

    if pattern_to_match is None or pattern_to_match == "":
        logger.critical("Pattern to match cannot be None or empty")
        raise ValueError("Pattern to match cannot be None or empty")

    files: list[RemoteAsset] = []
    minimum_age_seconds = convert_to_seconds(minimum_age)
    maximum_age_seconds = convert_to_seconds(maximum_age)

    # if pattern contains a %
    if "%" in pattern_to_match:
        updated_pattern = reference_date.strftime(pattern_to_match)
        logger.info(
            f"Pattern contains a %, replacing {pattern_to_match} with {updated_pattern}"
        )
        pattern_to_match = updated_pattern

    match remote_type:
        case RemoteConnectionType.LOCAL:
            if not remote_folder.exists():
                logger.info(f"Remote (local!) folder {remote_folder} does not exist")
                return []

            for file in (remote_folder).glob(pattern_to_match):
                if file.is_file():
                    file_stat = file.stat()
                    last_modified = datetime.fromtimestamp(
                        file_stat.st_mtime, tz=timezone.utc
                    )
                    size = file_stat.st_size
                    apply_filters_and_append_to_list(
                        file,
                        last_modified,
                        size,
                        files,
                        minimum_age_seconds,
                        maximum_age_seconds,
                        reference_date,
                    )

        case RemoteConnectionType.SFTP:
            transport = None
            sftp = None
            try:
                transport, sftp = connect_to_sftp_remote(
                    host, port, username, password, private_key_path
                )

                logger.debug(f"SFTP chdir '{remote_folder}'")
                try:
                    sftp.chdir(str(remote_folder))
                except FileNotFoundError:
                    logger.info(f"{remote_folder} does not exist")
                    return []

                logger.info(
                    f"Listing files in '{remote_folder}' matching '{pattern_to_match}'"
                )

                for filename in sftp.listdir():
                    if fnmatch.fnmatch(filename, pattern_to_match):
                        remote_file_path = remote_folder / filename

                        file_info = sftp.stat(filename)
                        st_mtime = file_info.st_mtime
                        if st_mtime is None:
                            logger.warning(
                                f"File {remote_file_path} has no modification time, skipping"
                            )
                            continue
                        timestamp: float = float(st_mtime)
                        last_modified = datetime.fromtimestamp(
                            timestamp, tz=timezone.utc
                        )
                        apply_filters_and_append_to_list(
                            remote_file_path,
                            last_modified,
                            file_info.st_size,
                            files,
                            minimum_age_seconds,
                            maximum_age_seconds,
                            reference_date,
                        )

            finally:
                if sftp is not None:
                    sftp.close()
                if transport is not None:
                    transport.close()

        case RemoteConnectionType.RCLONE:
            rclone_command = (
                RCloneCommandBuilder(rclone_config_file, rclone_config)
                .lsf(remote_folder, pattern_to_match=pattern_to_match)
                .build()
            )  # command outputs in "tsp" format (time, size, path)

            return_code, config_after, captured_output, exception = invoke_rclone(
                rclone_command,
                config_file_contents=(
                    rclone_config.get_config() if rclone_config else None
                ),
                logger=logger,
                capture_std_output=True,  # Capture output for processing
            )

            if type(exception) is FileNotFoundError:
                logger.error(
                    f"Remote folder {remote_folder} does not exist, rclone returned FileNotFoundError"
                )
            elif return_code != 0:
                logger.error(
                    f"Failed to list files in {remote_folder} with rclone, return code {return_code}"
                )
                raise exception or RuntimeError(
                    f"Failed to list files in {remote_folder} with rclone, return code {return_code}"
                )
            elif captured_output is None:
                logger.error(
                    "Captured output is None, something went wrong with rclone command"
                )

            for line in captured_output or []:
                line = line.strip()
                if not line:
                    continue

                parts = line.split(";")
                if len(parts) < 3:
                    logger.warning(
                        f"Line '{line}' does not have enough parts, skipping"
                    )
                    continue

                last_modified_str, size_str, file_name = parts
                try:
                    last_modified = datetime.fromisoformat(last_modified_str)
                    if last_modified.tzinfo is None:
                        last_modified = last_modified.replace(tzinfo=timezone.utc)
                except ValueError as e:
                    logger.error(
                        f"Failed to parse last modified time '{last_modified_str}': {e}"
                    )
                    continue

                try:
                    size = int(size_str)
                except ValueError as e:
                    logger.error(f"Failed to parse size '{size_str}': {e}")
                    continue

                remote_file_path = remote_folder / Path(file_name)

                apply_filters_and_append_to_list(
                    remote_file_path,
                    last_modified,
                    size,
                    files,
                    minimum_age_seconds,
                    maximum_age_seconds,
                    reference_date,
                )

            if return_code == 0 and rclone_config is not None and config_after:
                logger.info(
                    f"Updating rclone config for remote {rclone_config.remote_name}"
                )
                await rclone_config.update_config(config_after)

        case _:
            logger.critical(f"Unknown destination type {remote_type}")
            raise ValueError(f"Unknown destination type {remote_type}")

    files = finalise_file_list(
        files,
        sort=sort,
        skip=skip,
        take=take,
    )

    if len(files) > 1:
        logger.info(
            f"Found {len(files)} files matching {pattern_to_match} in {remote_folder}"
        )
    return files


def finalise_file_list(
    files: list[RemoteAsset],
    sort: SortFilesBy,
    skip: int,
    take: int | None,
) -> list[RemoteAsset]:
    """
    Finalise the file list by sorting and applying skip and take.
    """

    logger.debug(f"Finalising file list with sort {sort}, skip {skip}, take {take}")

    # default is to order by file name
    sorter = sort.get_sort_by_lambda_tuple()
    files.sort(key=sorter[0], reverse=sorter[1])
    files = files[skip:]  # skip the first 'skip' files
    if take is not None:
        files = files[:take]

    if not files:
        logger.info("Zero files found")

    return files


def apply_filters_and_append_to_list(
    file,
    last_modified,
    size,
    files,
    minimum_age_seconds: int,
    maximum_age_seconds: int,
    reference_date: datetime,
) -> bool:
    if size == 0:
        logger.warning(f"File {file} is zero bytes, skipping")
        return False

    # ensure last mod is in UTC
    if last_modified.tzinfo is None:
        raise ValueError(
            f"Last modified time {last_modified} for file {file} must be timezone aware"
        )

    last_modified_UTC = last_modified.astimezone(timezone.utc)
    reference_date_UTC = reference_date.astimezone(timezone.utc)

    # Only transfer files older than minimum_age_seconds
    if minimum_age_seconds and last_modified_UTC > (
        reference_date_UTC - timedelta(seconds=minimum_age_seconds)
    ):
        logger.info(
            f"File {file} last modified {last_modified_UTC} is newer than minimum age {minimum_age_seconds} seconds, skipping"
        )
        return False

    # Only transfer files younger than maximum_age_seconds
    if maximum_age_seconds and last_modified_UTC < (
        reference_date_UTC - timedelta(seconds=maximum_age_seconds)
    ):
        logger.info(
            f"File {file} last modified {last_modified_UTC} is older than maximum age {maximum_age_seconds} seconds, skipping"
        )
        return False

    logger.info(f"Found {file} modified {last_modified_UTC} size {size}b")
    files.append(RemoteAsset(file, last_modified_UTC, size))
    return True
