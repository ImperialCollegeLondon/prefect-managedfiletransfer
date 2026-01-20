from pathlib import Path
from prefect import flow, get_run_logger
from prefect.runtime import flow_run
from prefect.filesystems import LocalFileSystem

from prefect_managedfiletransfer.RCloneConfigSavedInPrefect import (
    RCloneConfigSavedInPrefect,
)
from prefect_managedfiletransfer.RemoteConnectionType import RemoteConnectionType
from prefect_managedfiletransfer.ServerWithPublicKeyAuthBlock import (
    ServerWithPublicKeyAuthBlock,
)
from prefect_managedfiletransfer.RCloneConfigFileBlock import RCloneConfigFileBlock

from prefect_managedfiletransfer.constants import CONSTANTS


from prefect_managedfiletransfer.ServerWithBasicAuthBlock import (
    ServerWithBasicAuthBlock,
)
from prefect_managedfiletransfer.upload_asset import upload_asset
from prefect_managedfiletransfer.TransferType import TransferType
from prefect_managedfiletransfer.block_utils import try_fetch_block


def generate_flow_run_name() -> str:
    parameters = flow_run.parameters
    source_file = parameters["pattern_to_upload"]
    destination_file = parameters["destination_file"].name

    if source_file == destination_file:
        return f"Upload-{source_file}"
    else:
        return f"Upload-{source_file}-to-{destination_file}"


@flow(
    name=CONSTANTS.FLOW_NAMES.UPLOAD_FILE,
    log_prints=True,
    flow_run_name=generate_flow_run_name,
    retries=2,
    retry_delay_seconds=60 * 20,  # retry every 20 minutes
    timeout_seconds=60 * 30,  # timeout after 30 minutes
)
async def upload_file_flow(
    source_folder: Path,
    pattern_to_upload: str,
    destination_file: Path,
    destination_block_or_blockname: (
        ServerWithBasicAuthBlock
        | ServerWithPublicKeyAuthBlock
        | LocalFileSystem
        | RCloneConfigFileBlock
        | str
    ),
    update_only_if_newer_mode: bool = False,  # if true skip files that are newer on the destination
    mode: TransferType = TransferType.Copy,
    overwrite: bool = False,
):
    """
    Publish a single file to a destination, e.g. upload an image to a website or copy a file to a local shared public folder

    Args:
        source_folder (Path): The folder where the file to upload is located.
        pattern_to_upload (str): The pattern of the file to upload, e.g. "*.jpg".
        destination_file (Path): The destination file path where the file will be uploaded.
        destination_block_or_blockname (ServerWithBasicAuthBlock | ServerWithPublicKeyAuthBlock | LocalFileSystem | RCloneConfigFileBlock | str): The destination block or block name where the file will be uploaded.
        update_only_if_newer_mode (bool): If true, skip files that are newer on the destination.
        mode (TransferType): The transfer mode to use, e.g. Copy or Move.
        overwrite (bool): If true, overwrite the file if it already exists at the destination.
    Returns:
        None: The function does not return anything, it raises an exception if the upload fails.
    Raises:
        ValueError: If the destination block or blockname is missing, or if the upload fails.
        TypeError: If the destination block is of an unsupported type.
        ImportError: If the required libraries for SFTP or RClone are not installed.
        FileNotFoundError: If the source folder or file to upload does not exist.
        ConnectionError: If the connection to the SFTP server fails.
        FileExistsError: If the destination file already exists and overwrite is False.
        RuntimeError: if the upload occured but the sizes do not match, indicating a potential issue with the upload process.
        RuntimeError: if the upload fails with a non-zero exit code.
    """

    logger = get_run_logger()

    sftp_details: ServerWithBasicAuthBlock | None = None
    sftp_details_public_key: ServerWithPublicKeyAuthBlock | None = None
    local_details: LocalFileSystem | None = None

    if destination_block_or_blockname is None:
        raise ValueError("Destination block or blockname is missing")

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
    result: int | None = None
    if isinstance(destination_block, ServerWithBasicAuthBlock):
        sftp_details = destination_block
        if not sftp_details.isValid():
            raise ValueError("One or more SFTP server details are missing")
        logger.info(
            f"Uploading {pattern_to_upload} to {destination_file} on {sftp_details.host}"
        )
        result = await upload_asset(
            source_folder=source_folder,
            pattern_to_upload=pattern_to_upload,
            destination_file=destination_file,
            destination_type=RemoteConnectionType.SFTP,
            host=sftp_details.host,
            port=sftp_details.port,
            username=sftp_details.username,
            password=sftp_details.password.get_secret_value(),
            update_only_if_newer_mode=update_only_if_newer_mode,
            overwrite=overwrite,
            mode=mode,
        )
    elif isinstance(destination_block, ServerWithPublicKeyAuthBlock):
        sftp_details_public_key = destination_block
        if not sftp_details_public_key.is_valid():
            raise ValueError("One or more SFTP server details are missing")
        logger.info(
            f"Uploading {pattern_to_upload} to {destination_file} on {sftp_details_public_key.host} with pub/private keys"
        )
        with sftp_details_public_key.get_temp_key_file() as temp_key_file:
            result = await upload_asset(
                source_folder=source_folder,
                pattern_to_upload=pattern_to_upload,
                destination_file=destination_file,
                destination_type=RemoteConnectionType.SFTP,
                host=sftp_details_public_key.host,
                port=sftp_details_public_key.port,
                username=sftp_details_public_key.username,
                private_key_path=temp_key_file.get_path(),
                update_only_if_newer_mode=update_only_if_newer_mode,
                overwrite=overwrite,
                mode=mode,
            )
    elif isinstance(destination_block, LocalFileSystem):
        local_details = destination_block
        if not local_details.basepath:
            raise ValueError("LocalFileSystem.basepath details are missing")
        logger.debug(f"Using basepath from local filesystem: {local_details.basepath}")
        destination_file = Path(local_details.basepath) / destination_file
        logger.info(f"Uploading to local filesystem: {destination_file}")
        result = await upload_asset(
            source_folder=source_folder,
            pattern_to_upload=pattern_to_upload,
            destination_file=destination_file,
            destination_type=RemoteConnectionType.LOCAL,
            update_only_if_newer_mode=update_only_if_newer_mode,
            overwrite=overwrite,
            mode=mode,
        )
    elif isinstance(destination_block, RCloneConfigFileBlock):
        rclone_details_prefect_block: RCloneConfigFileBlock = destination_block
        logger.info(
            f"Uploading {pattern_to_upload} to {destination_file} using rclone block for remote {rclone_details_prefect_block.remote_name}"
        )

        result = await upload_asset(
            source_folder=source_folder,
            pattern_to_upload=pattern_to_upload,
            destination_file=destination_file,
            destination_type=RemoteConnectionType.RCLONE,
            rclone_config=RCloneConfigSavedInPrefect(rclone_details_prefect_block),
            update_only_if_newer_mode=update_only_if_newer_mode,
            overwrite=overwrite,
            mode=mode,
            logger=logger,
        )

    if result is None:
        raise ValueError("Destination details are missing")
    if result != 0:
        raise RuntimeError(
            f"Failed to upload {pattern_to_upload} to {destination_file}. Exit code {result}"
        )
