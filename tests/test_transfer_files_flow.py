from prefect import State
from prefect_managedfiletransfer import FileMatcher, TransferType, transfer_files_flow
from prefect.filesystems import LocalFileSystem
import pytest

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_transfer_files_flow_can_copy_locally(
    prefect_db, temp_folder_path, temp_file_path
):
    source = LocalFileSystem(basepath=temp_file_path.parent)
    destination = LocalFileSystem(basepath=temp_folder_path)
    assert source.basepath != destination.basepath

    result = await transfer_files_flow(
        source_block_or_blockname=source,
        destination_block_or_blockname=destination,
        source_file_matchers=[
            FileMatcher(
                source_folder=temp_file_path.parent,
                pattern_to_match=temp_file_path.name,
            )
        ],
        mode=TransferType.Copy,
        check_for_space_overhead=1024 * 1024 * 10,
    )

    assert isinstance(result, list)
    assert len(result) == 1
    assert temp_folder_path.joinpath(temp_file_path.name).exists(), (
        "File should be copied to destination folder"
    )


@pytest.mark.asyncio
async def test_transfer_files_flow_can_move_locally(
    prefect_db, temp_folder_path, temp_file_path
):
    source = LocalFileSystem(basepath=temp_file_path.parent)
    destination = LocalFileSystem(basepath=temp_folder_path)
    assert source.basepath != destination.basepath

    result = await transfer_files_flow(
        source_block_or_blockname=source,
        destination_block_or_blockname=destination,
        source_file_matchers=[
            FileMatcher(
                source_folder=temp_file_path.parent,
                pattern_to_match=temp_file_path.name,
            )
        ],
        mode=TransferType.Move,
        check_for_space=False,
    )

    assert isinstance(result, list)
    assert len(result) == 1
    assert not temp_file_path.exists(), "File should be moved from source folder"
    assert temp_folder_path.joinpath(temp_file_path.name).exists(), (
        "File should be moved to destination folder"
    )


@pytest.mark.asyncio
async def test_transfer_files_flow_can_ignore_files(
    prefect_db, temp_folder_path, temp_file_path
):
    source = LocalFileSystem(basepath=temp_file_path.parent)
    destination = LocalFileSystem(basepath=temp_folder_path)
    assert source.basepath != destination.basepath

    result = await transfer_files_flow(
        source_block_or_blockname=source,
        destination_block_or_blockname=destination,
        source_file_matchers=[
            FileMatcher(
                source_folder=temp_file_path.parent, pattern_to_match="Not-a-file"
            )
        ],
        mode=TransferType.Move,
        return_state=True,
    )

    assert isinstance(result, State)
    assert result.is_completed()
    assert result.name == "Skipped"

    assert temp_file_path.exists(), "File should NOT be moved from source folder"
    assert not temp_folder_path.joinpath(temp_file_path.name).exists(), (
        "File should not be moved to destination folder"
    )


@pytest.mark.asyncio
async def test_transfer_files_flow_with_block_name_strings(
    prefect_db, temp_folder_path, temp_file_path
):
    """Test that flow can load blocks by name (string parameters)."""
    source = LocalFileSystem(basepath=temp_file_path.parent)
    destination = LocalFileSystem(basepath=temp_folder_path)
    assert source.basepath != destination.basepath

    # Save blocks with names
    await source.save("test-transfer-source-block")
    await destination.save("test-transfer-dest-block")

    # Call flow with block names as strings
    result = await transfer_files_flow(
        source_block_or_blockname="test-transfer-source-block",
        destination_block_or_blockname="test-transfer-dest-block",
        source_file_matchers=[
            FileMatcher(
                source_folder=temp_file_path.parent,
                pattern_to_match=temp_file_path.name,
            )
        ],
        mode=TransferType.Copy,
        check_for_space_overhead=1024 * 1024 * 10,
    )

    assert isinstance(result, list)
    assert len(result) == 1
    assert temp_folder_path.joinpath(temp_file_path.name).exists(), (
        "File should be copied to destination folder"
    )
