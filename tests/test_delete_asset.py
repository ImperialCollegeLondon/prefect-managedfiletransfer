#!/usr/bin/env python
"""Tests for `delete_asset` package."""
# pylint: disable=redefined-outer-name

import logging
from pathlib import Path

import pytest

from prefect_managedfiletransfer.delete_asset import delete_asset
from prefect_managedfiletransfer.RemoteAsset import RemoteAsset
from prefect_managedfiletransfer.RemoteConnectionType import RemoteConnectionType

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_delete_asset_local_file(temp_file_path):
    """Test deleting a local file."""
    # Verify file exists
    assert temp_file_path.exists()

    # Create RemoteAsset
    remote_asset = RemoteAsset(
        path=temp_file_path, last_modified=None, size=temp_file_path.stat().st_size
    )

    # Delete the file
    await delete_asset(file=remote_asset, remote_type=RemoteConnectionType.LOCAL)

    # Verify file was deleted
    assert not temp_file_path.exists()


@pytest.mark.asyncio
async def test_delete_asset_local_file_that_does_not_exist(temp_file_path, caplog):
    """Test deleting a local file that doesn't exist - should not error."""
    # Delete the file first
    temp_file_path.unlink()
    assert not temp_file_path.exists()

    # Create RemoteAsset
    remote_asset = RemoteAsset(path=temp_file_path, last_modified=None, size=0)

    caplog.set_level(logging.WARNING)

    # Delete the file (should not raise exception)
    await delete_asset(file=remote_asset, remote_type=RemoteConnectionType.LOCAL)

    # Verify warning was logged
    assert any("does not exist" in message for message in caplog.text.splitlines())


@pytest.mark.asyncio
async def test_delete_asset_sftp_file(
    sftp_server, temp_file_path, sftp_creds, sftp_client
):
    """Test deleting a file via SFTP."""
    # Set up: upload a file to SFTP server
    source_path = Path("upload/") / "test_delete.txt"
    temp_file_path.write_bytes(b"test delete content")

    sftp_client.chdir(source_path.parent.as_posix())
    sftp_client.put(
        localpath=temp_file_path.absolute().as_posix(),
        remotepath=source_path.name,
    )

    # Verify file exists on SFTP server
    assert sftp_client.stat(source_path.name) is not None

    # Create RemoteAsset
    remote_asset = RemoteAsset(path=source_path, last_modified=None, size=0)

    host_ip = sftp_server.get_container_host_ip()
    host_port = sftp_server.get_exposed_sftp_port()

    # Delete the file
    await delete_asset(
        file=remote_asset,
        remote_type=RemoteConnectionType.SFTP,
        host=host_ip,
        port=host_port,
        username=sftp_creds.name,
        password=sftp_creds.password,
    )

    # Verify file was deleted
    with pytest.raises(FileNotFoundError):
        sftp_client.stat(source_path.name)


@pytest.mark.asyncio
async def test_delete_asset_sftp_file_that_does_not_exist(
    sftp_server, sftp_creds, caplog
):
    """Test deleting a file via SFTP that doesn't exist - should not error."""
    source_path = Path("upload/") / "nonexistent.txt"

    # Create RemoteAsset
    remote_asset = RemoteAsset(path=source_path, last_modified=None, size=0)

    host_ip = sftp_server.get_container_host_ip()
    host_port = sftp_server.get_exposed_sftp_port()

    caplog.set_level(logging.WARNING)

    # Delete the file (should not raise exception)
    await delete_asset(
        file=remote_asset,
        remote_type=RemoteConnectionType.SFTP,
        host=host_ip,
        port=host_port,
        username=sftp_creds.name,
        password=sftp_creds.password,
    )

    # Verify warning was logged
    assert any("does not exist" in message for message in caplog.text.splitlines())


@pytest.mark.asyncio
async def test_delete_asset_sftp_folder_does_not_exist_raises_error(
    sftp_server, sftp_creds
):
    """Test deleting a file from a folder that doesn't exist raises error."""
    source_path = Path("nonexistent_folder/") / "test.txt"

    # Create RemoteAsset
    remote_asset = RemoteAsset(path=source_path, last_modified=None, size=0)

    host_ip = sftp_server.get_container_host_ip()
    host_port = sftp_server.get_exposed_sftp_port()

    # Delete the file (should raise exception)
    with pytest.raises(FileNotFoundError) as exc_info:
        await delete_asset(
            file=remote_asset,
            remote_type=RemoteConnectionType.SFTP,
            host=host_ip,
            port=host_port,
            username=sftp_creds.name,
            password=sftp_creds.password,
        )

    assert "does not exist" in str(exc_info.value)


@pytest.mark.asyncio
async def test_delete_asset_rclone_local_file(temp_file_path):
    """Test deleting a local file via rclone."""
    # Verify file exists
    assert temp_file_path.exists()

    # Create RemoteAsset
    remote_asset = RemoteAsset(
        path=temp_file_path, last_modified=None, size=temp_file_path.stat().st_size
    )

    # Delete the file via rclone
    await delete_asset(
        file=remote_asset,
        remote_type=RemoteConnectionType.RCLONE,
        rclone_config_file=None,
        rclone_config=None,
    )

    # Verify file was deleted
    assert not temp_file_path.exists()


@pytest.mark.asyncio
async def test_delete_asset_with_none_file_raises_error():
    """Test that passing None as file raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        await delete_asset(file=None, remote_type=RemoteConnectionType.LOCAL)

    assert "cannot be None" in str(exc_info.value)


@pytest.mark.asyncio
async def test_delete_asset_with_invalid_remote_type_raises_error(temp_file_path):
    """Test that passing an invalid remote type raises ValueError."""
    remote_asset = RemoteAsset(
        path=temp_file_path, last_modified=None, size=temp_file_path.stat().st_size
    )

    # This should raise ValueError for unknown remote type
    with pytest.raises(ValueError) as exc_info:
        await delete_asset(file=remote_asset, remote_type="INVALID")

    assert "Unknown remote type" in str(exc_info.value)
