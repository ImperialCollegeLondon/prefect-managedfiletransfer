import logging
from pathlib import Path
from prefect_managedfiletransfer.RemoteAsset import RemoteAsset
from prefect_managedfiletransfer.RemoteConnectionType import RemoteConnectionType
from prefect_managedfiletransfer.RCloneConfig import RCloneConfig
from prefect_managedfiletransfer.RCloneCommandBuilder import RCloneCommandBuilder
from prefect_managedfiletransfer.invoke_rclone import invoke_rclone
from prefect_managedfiletransfer.sftp_utils import connect_to_sftp_remote

logger = logging.getLogger(__name__)


async def delete_asset(
    file: RemoteAsset,
    remote_type: RemoteConnectionType,
    host: str | None = None,
    port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    private_key_path: (Path | None) = None,
    rclone_config_file: Path | None = None,
    rclone_config: RCloneConfig | None = None,
) -> None:
    """
    Delete a file from a remote source (SFTP, RClone, or LocalFileSystem).

    Args:
        file: The remote asset to delete.
        remote_type: The type of the remote connection.
        host: The host of the remote connection (for SFTP).
        port: The port of the remote connection (for SFTP).
        username: The username for the remote connection (for SFTP).
        password: The password for the remote connection (for SFTP).
        private_key_path: The path to the private key file (for SFTP with public/private key auth).
        rclone_config_file: The path to the rclone config file (for RClone).
        rclone_config: The rclone config object (for RClone).
    """

    if file is None or (hasattr(file, "path") and file.path is None):
        logger.critical("File to delete cannot be None or empty")
        raise ValueError("File to delete cannot be None or empty")

    if rclone_config_file is not None and rclone_config is not None:
        raise ValueError(
            "rclone_config_file and rclone_config cannot be used at the same time"
        )

    remote_type_name = (
        remote_type.name if hasattr(remote_type, "name") else str(remote_type)
    )
    logger.debug(f"Deleting file {file.path} from {remote_type_name} remote")

    match remote_type:
        case RemoteConnectionType.LOCAL:
            if not file.path.exists():
                logger.warning(
                    f"Local file {file.path} does not exist, skipping deletion"
                )
                return

            logger.debug(f"Deleting local file {file.path}")
            file.path.unlink()
            logger.info(f"Deleted local file {file.path}")

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
                    raise FileNotFoundError(message)

                logger.info(f"Deleting remote file {file.path.name}")
                try:
                    sftp.remove(file.path.name)
                    logger.info(f"Deleted remote file {file.path.name}")
                except FileNotFoundError:
                    message = f"Remote file {file.path.name} does not exist"
                    logger.warning(message)

            finally:
                if sftp is not None:
                    sftp.close()
                if transport is not None:
                    transport.close()

        case RemoteConnectionType.RCLONE:
            logger.debug(f"Deleting remote file {file.path} with rclone")

            return_code, config_after, captured_output, exception = invoke_rclone(
                RCloneCommandBuilder(rclone_config_file, rclone_config)
                .deleteFile(file.path)
                .build(),
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

            if return_code != 0 and type(exception) is not FileNotFoundError:
                logger.error(
                    f"Failed to delete remote file {file.path} with rclone, return code {return_code}"
                )
                raise RuntimeError(
                    f"Failed to delete remote file {file.path} with rclone, return code {return_code}"
                )
            else:
                logger.info(f"Deleted remote file {file.path}")

        case _:
            logger.critical(f"Unknown remote type {remote_type}")
            raise ValueError(f"Unknown remote type {remote_type}")
