#!/usr/bin/env python
"""Tests for `delete_files_flow` package."""
# pylint: disable=redefined-outer-name

from prefect import State
from prefect_managedfiletransfer import FileMatcher, delete_files_flow
from prefect_managedfiletransfer.ServerWithBasicAuthBlock import (
    ServerWithBasicAuthBlock,
)
from prefect.filesystems import LocalFileSystem
import pytest
from pathlib import Path

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_delete_files_flow_can_delete_local_file(prefect_db, temp_file_path):
    """Test deleting a single local file."""
    source = LocalFileSystem(basepath=temp_file_path.parent)

    # Verify file exists before deletion
    assert temp_file_path.exists()

    result = await delete_files_flow(
        source_block_or_blockname=source,
        source_file_matchers=[
            FileMatcher(
                source_folder=temp_file_path.parent,
                pattern_to_match=temp_file_path.name,
            )
        ],
    )

    assert isinstance(result, list)
    assert len(result) == 1
    assert not temp_file_path.exists(), "File should be deleted from source folder"


@pytest.mark.asyncio
async def test_delete_files_flow_can_delete_multiple_local_files(
    prefect_db, temp_folder_path
):
    """Test deleting multiple local files."""
    # Create multiple test files
    file1 = temp_folder_path / "test1.txt"
    file2 = temp_folder_path / "test2.txt"
    file3 = temp_folder_path / "test3.txt"

    file1.write_text("test content 1")
    file2.write_text("test content 2")
    file3.write_text("test content 3")

    source = LocalFileSystem(basepath=temp_folder_path)

    # Verify files exist before deletion
    assert file1.exists()
    assert file2.exists()
    assert file3.exists()

    result = await delete_files_flow(
        source_block_or_blockname=source,
        source_file_matchers=[
            FileMatcher(
                source_folder=temp_folder_path,
                pattern_to_match="test*.txt",
            )
        ],
    )

    assert isinstance(result, list)
    assert len(result) == 3
    assert not file1.exists(), "File 1 should be deleted"
    assert not file2.exists(), "File 2 should be deleted"
    assert not file3.exists(), "File 3 should be deleted"


@pytest.mark.asyncio
async def test_delete_files_flow_with_no_matching_files(
    prefect_db, temp_folder_path, temp_file_path
):
    """Test that flow handles no matching files gracefully."""
    source = LocalFileSystem(basepath=temp_file_path.parent)

    result = await delete_files_flow(
        source_block_or_blockname=source,
        source_file_matchers=[
            FileMatcher(
                source_folder=temp_file_path.parent,
                pattern_to_match="nonexistent-file.txt",
            )
        ],
        return_state=True,
    )

    assert isinstance(result, State)
    assert result.is_completed()
    assert result.name == "Skipped"

    assert temp_file_path.exists(), "Original file should still exist"


@pytest.mark.asyncio
async def test_delete_files_flow_with_multiple_matchers(prefect_db, temp_folder_path):
    """Test deleting files using multiple matchers."""
    # Create test files
    file1 = temp_folder_path / "test1.txt"
    file2 = temp_folder_path / "data.csv"
    file3 = temp_folder_path / "test2.txt"

    file1.write_text("test content 1")
    file2.write_text("csv content")
    file3.write_text("test content 2")

    source = LocalFileSystem(basepath=temp_folder_path)

    # Verify files exist before deletion
    assert file1.exists()
    assert file2.exists()
    assert file3.exists()

    result = await delete_files_flow(
        source_block_or_blockname=source,
        source_file_matchers=[
            FileMatcher(
                source_folder=temp_folder_path,
                pattern_to_match="test*.txt",
            ),
            FileMatcher(
                source_folder=temp_folder_path,
                pattern_to_match="*.csv",
            ),
        ],
    )

    assert isinstance(result, list)
    assert len(result) == 3
    assert not file1.exists(), "Test file 1 should be deleted"
    assert not file2.exists(), "CSV file should be deleted"
    assert not file3.exists(), "Test file 2 should be deleted"


@pytest.mark.asyncio
async def test_delete_files_flow_sftp(
    prefect_db, sftp_server, temp_file_path, sftp_creds, sftp_client
):
    """Test deleting files via SFTP."""
    # Set up: upload files to SFTP server
    source_path1 = Path("upload/") / "delete_test1.txt"
    source_path2 = Path("upload/") / "delete_test2.txt"

    temp_file_path.write_bytes(b"test delete content 1")

    sftp_client.chdir(source_path1.parent.as_posix())
    sftp_client.put(
        localpath=temp_file_path.absolute().as_posix(),
        remotepath=source_path1.name,
    )
    sftp_client.put(
        localpath=temp_file_path.absolute().as_posix(),
        remotepath=source_path2.name,
    )

    # Verify files exist on SFTP server
    assert sftp_client.stat(source_path1.name) is not None
    assert sftp_client.stat(source_path2.name) is not None

    host_ip = sftp_server.get_container_host_ip()
    host_port = sftp_server.get_exposed_sftp_port()

    source_block = ServerWithBasicAuthBlock(
        host=host_ip,
        port=host_port,
        username=sftp_creds.name,
        password=sftp_creds.password,
    )

    result = await delete_files_flow(
        source_block_or_blockname=source_block,
        source_file_matchers=[
            FileMatcher(
                source_folder=source_path1.parent,
                pattern_to_match="delete_test*.txt",
            )
        ],
    )

    assert isinstance(result, list)
    assert len(result) == 2

    # Verify files were deleted
    with pytest.raises(FileNotFoundError):
        sftp_client.stat(source_path1.name)
    with pytest.raises(FileNotFoundError):
        sftp_client.stat(source_path2.name)


@pytest.mark.asyncio
async def test_delete_files_flow_preserves_non_matching_files(
    prefect_db, temp_folder_path
):
    """Test that flow only deletes matching files and preserves others."""
    # Create test files
    file_to_delete = temp_folder_path / "delete_me.txt"
    file_to_keep = temp_folder_path / "keep_me.log"

    file_to_delete.write_text("delete this")
    file_to_keep.write_text("keep this")

    source = LocalFileSystem(basepath=temp_folder_path)

    # Verify files exist before deletion
    assert file_to_delete.exists()
    assert file_to_keep.exists()

    result = await delete_files_flow(
        source_block_or_blockname=source,
        source_file_matchers=[
            FileMatcher(
                source_folder=temp_folder_path,
                pattern_to_match="delete_*.txt",
            )
        ],
    )

    assert isinstance(result, list)
    assert len(result) == 1
    assert not file_to_delete.exists(), "Matching file should be deleted"
    assert file_to_keep.exists(), "Non-matching file should be preserved"


@pytest.mark.asyncio
async def test_delete_files_flow_with_block_name_string(prefect_db, temp_folder_path):
    """Test that flow can load a block by name (string parameter)."""
    # Create test file
    file_to_delete = temp_folder_path / "test_blockname.txt"
    file_to_delete.write_text("test content")

    # Create and save a block with a name
    source = LocalFileSystem(basepath=temp_folder_path)
    await source.save("test-delete-source-block")

    # Verify file exists before deletion
    assert file_to_delete.exists()

    # Call flow with block name as string
    result = await delete_files_flow(
        source_block_or_blockname="test-delete-source-block",
        source_file_matchers=[
            FileMatcher(
                source_folder=temp_folder_path,
                pattern_to_match="test_blockname.txt",
            )
        ],
    )

    assert isinstance(result, list)
    assert len(result) == 1
    assert not file_to_delete.exists(), "File should be deleted"
