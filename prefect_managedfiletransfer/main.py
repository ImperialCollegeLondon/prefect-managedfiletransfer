"""Main module."""

import asyncio
import logging
from pathlib import Path
import sys
from prefect_managedfiletransfer.RemoteConnectionType import RemoteConnectionType
from prefect_managedfiletransfer.upload_asset import upload_asset
from prefect_managedfiletransfer.TransferType import TransferType
from prefect_managedfiletransfer.download_asset import download_asset
from prefect_managedfiletransfer.list_remote_assets import list_remote_assets
from prefect_managedfiletransfer.constants import CONSTANTS

# cli
import typer
from rich.console import Console
from rich.table import Table


app = typer.Typer()
globalState = {"verbose": False}
logger = logging.getLogger(__name__)
console = Console()


@app.command()
def hello(name: str):
    print(f"Hello {name}")


@app.callback()
def main(verbose: bool = False):
    if verbose:
        globalState["verbose"] = True
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    else:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO)


@app.command(name="upload", help="Upload an asset to the SOLO website")
def upload_asset_cli(
    source_folder: Path = typer.Option(
        help="Path to the folder containing the asset to upload",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        writable=False,
    ),
    pattern_to_upload: str = typer.Option(
        help="Pattern to match the asset to upload",
    ),
    destination_file: Path = typer.Option(
        help="Path to the file to upload to",
        exists=False,
        file_okay=True,
        dir_okay=False,
        readable=True,
        writable=False,
    ),
    destination_type: RemoteConnectionType = typer.Option(
        RemoteConnectionType.LOCAL,
        help="Type of destination to upload to",
        case_sensitive=False,
    ),
    host: str | None = typer.Option(
        None,
        help="Host to upload the file to (only needed for SFTP destination)",
    ),
    port: int | None = typer.Option(
        None,
        help="Port to upload the file to (only needed for SFTP destination)",
    ),
    username: str | None = typer.Option(
        None,
        envvar=CONSTANTS.ENV_VAR_NAMES.PMFTUPLOAD_USERNAME,
        help="Username to upload the file to (only needed for SFTP destination)",
    ),
    password: str | None = typer.Option(
        None,
        envvar=CONSTANTS.ENV_VAR_NAMES.PMFTUPLOAD_PASSWORD,
        help="Password to upload the file to (only needed for SFTP destination)",
    ),
    private_key_path: Path | None = typer.Option(
        None,
        help="Path to the private key file for SFTP with public/private key authentication",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    config: Path | None = typer.Option(
        None,
        help="Path to the rclone config file to use for upload",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        writable=True,
    ),
    update_only_if_newer_mode: bool = typer.Option(
        False,
        "--update",
        help="If true, skip files that are newer on the destination",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite/--no-overwrite",
        help="Flag to allow files already in destination to be overwritten",
    ),
    move: bool = typer.Option(False, "--move/--copy"),
    check_space: bool = typer.Option(
        False,
        "--check-space/--no-check-space",
        help="Check for space on the destination before uploading. If there is not enough space, the upload will be skipped",
    ),
    check_space_overhead: int = typer.Option(
        0,
        "--check-space-overhead",
        help=(
            "Overhead in bytes to consider when checking for space on the destination. "
            "If the destination does not have enough space, the upload will fail"
        ),
    ),
):
    code = asyncio.run(
        upload_asset(
            source_folder=source_folder,
            pattern_to_upload=pattern_to_upload,
            destination_file=destination_file,
            destination_type=destination_type,
            host=host,
            port=port,
            username=username,
            password=password,
            private_key_path=private_key_path,
            rclone_config_file=config,
            update_only_if_newer_mode=update_only_if_newer_mode,
            overwrite=overwrite,
            mode=TransferType.Move if move else TransferType.Copy,
            check_for_space=check_space,
            check_for_space_overhead=check_space_overhead,
        )
    )

    if code != 0:
        raise typer.Exit(code=code)


@app.command(name="list", help="list remote assets")
def list_asset_cli(
    remote_folder: Path = typer.Option(
        help="Path of a remote folder containing the assets to list"
    ),
    pattern_to_match: str = typer.Option(
        help="Pattern to match filenames of the assets to be listed",
    ),
    min_age: str = typer.Option(
        None,
        help="Minimum age of the files to be listed in seconds or '1d 3h' style string. If not provided, all files will be listed.",
    ),
    max_age: str = typer.Option(
        None,
        help="Maximum age of the files to be listed in seconds or '1d 3h' style string. If not provided, all files will be listed.",
    ),
    take: int | None = None,  # how many to take, None for all
    skip: int = 0,  # how many to skip, default is 0
    remote_type: RemoteConnectionType = typer.Option(
        RemoteConnectionType.LOCAL,
        help="Type of destination to query",
        case_sensitive=False,
    ),
    host: str | None = typer.Option(
        None,
        help="Host to upload the file to (only needed for SFTP destination)",
    ),
    port: int | None = typer.Option(
        None,
        help="Port to upload the file to (only needed for SFTP destination)",
    ),
    username: str | None = typer.Option(
        None,
        envvar=CONSTANTS.ENV_VAR_NAMES.PMFTUPLOAD_USERNAME,
        help="Username to upload the file to (only needed for SFTP destination)",
    ),
    password: str | None = typer.Option(
        None,
        envvar=CONSTANTS.ENV_VAR_NAMES.PMFTUPLOAD_PASSWORD,
        help="Password to upload the file to (only needed for SFTP destination)",
    ),
    private_key_path: Path | None = typer.Option(
        None,
        help="Path to the private key file for SFTP with public/private key authentication",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    config: Path | None = typer.Option(
        None,
        help="Path to the rclone config file to use for listing",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        writable=True,
    ),
):
    async def get_assets():
        files = await list_remote_assets(
            remote_folder=remote_folder,
            pattern_to_match=pattern_to_match,
            remote_type=remote_type,
            host=host,
            port=port,
            username=username,
            password=password,
            private_key_path=private_key_path,
            rclone_config_file=config,
            minimum_age=min_age,
            maximum_age=max_age,
            take=take,
            skip=skip,
        )
        table = Table("Path", "Modified", "Size (bytes)")

        for file in files:
            table.add_row(
                str(file.path),
                file.last_modified.strftime("%Y-%m-%d %H:%M:%S"),
                str(file.size),
            )

        console.print(table)

        if len(files) == 0:
            raise typer.Exit(code=3)

    asyncio.run(get_assets())


@app.command(name="download", help="Download remote assets to a local folder")
def download_asset_cli(
    remote_folder: Path = typer.Option(
        help="Path of a remote folder containing the assets to list"
    ),
    pattern_to_match: str = typer.Option(
        help="Pattern to match filenames of the assets to be listed",
    ),
    destination_folder: Path = typer.Option(
        help="Path to the file to download files into",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        writable=True,
    ),
    remote_type: RemoteConnectionType = typer.Option(
        RemoteConnectionType.LOCAL,
        help="Type of destination to query",
        case_sensitive=False,
    ),
    host: str | None = typer.Option(
        None,
        help="Host to upload the file to (only needed for SFTP destination)",
    ),
    port: int | None = typer.Option(
        None,
        help="Port to upload the file to (only needed for SFTP destination)",
    ),
    username: str | None = typer.Option(
        None,
        envvar=CONSTANTS.ENV_VAR_NAMES.PMFTUPLOAD_USERNAME,
        help="Username to upload the file to (only needed for SFTP destination)",
    ),
    password: str | None = typer.Option(
        None,
        envvar=CONSTANTS.ENV_VAR_NAMES.PMFTUPLOAD_PASSWORD,
        help="Password to upload the file to (only needed for SFTP destination)",
    ),
    private_key_path: Path | None = typer.Option(
        None,
        help="Path to the private key file for SFTP with public/private key authentication",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    config: Path | None = typer.Option(
        None,
        help="Path to the rclone config file to use for listing",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        writable=True,
    ),
    update_only_if_newer_mode: bool = typer.Option(
        False,
        "--update",
        help="If true, skip files that are newer on the destination",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite/--no-overwrite",
        help="Flag to allow files already in destination to be overwritten",
    ),
    move: bool = typer.Option(False, "--move/--copy"),
    check_space: bool = typer.Option(
        False,
        "--check-space/--no-check-space",
        help="Check for space on the destination before uploading. If there is not enough space, the upload will be skipped",
    ),
    check_space_overhead: int = typer.Option(
        0,
        "--check-space-overhead",
        help=(
            "Overhead in bytes to consider when checking for space on the destination. "
            "If the destination does not have enough space, the upload will fail"
        ),
    ),
):
    async def download_assets_async():
        files = await list_remote_assets(
            remote_folder=remote_folder,
            pattern_to_match=pattern_to_match,
            remote_type=remote_type,
            host=host,
            port=port,
            username=username,
            password=password,
            private_key_path=private_key_path,
            rclone_config_file=config,
        )

        for file in files:
            result = await download_asset(
                file=file,
                destination_path=destination_folder / file.path.name,
                remote_type=remote_type,
                host=host,
                port=port,
                username=username,
                password=password,
                private_key_path=private_key_path,
                rclone_config_file=config,
                update_only_if_newer_mode=update_only_if_newer_mode,
                overwrite=overwrite,
                mode=TransferType.Move if move else TransferType.Copy,
                check_for_space=check_space,
                check_for_space_overhead=check_space_overhead,
            )
            if not result.success:
                logger.error(f"Failed to download {file.path}: {result.error}")
                raise typer.Exit(code=2)

        if len(files) == 0:
            raise typer.Exit(code=3)

    asyncio.run(download_assets_async())


if __name__ == "__main__":
    app()  # pragma: no cover
