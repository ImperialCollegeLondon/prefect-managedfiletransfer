#!/usr/bin/env python

import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path

from prefect_managedfiletransfer.upload_asset import upload_asset
from prefect_managedfiletransfer.main import app

import pytest

from typer.testing import CliRunner

runner = CliRunner()


def invoke_upload_command(
    source_folder: str,
    pattern_to_upload: str,
    destination_file: str,
    destination_type: str,
    additional_args: list = None,
    expect_failure: bool = False,
) -> None:
    """Helper function to invoke the upload command."""
    args = [
        "upload",
        "--source-folder",
        source_folder,
        "--pattern-to-upload",
        pattern_to_upload,
        "--destination-file",
        destination_file,
        "--destination-type",
        destination_type,
    ]
    if additional_args:
        args.extend(additional_args)

    result = runner.invoke(app, args)

    logging.debug("stderr: %s", result.stderr)
    logging.debug("stdout: %s", result.stdout)

    # Verify.
    if expect_failure:
        assert result.exit_code != 0
    else:
        if result.exception:
            raise result.exception
        assert result.exit_code == 0

    return result


def test_upload_asset_via_local_copy(temp_file_path) -> None:
    # Set up.
    destination_path = setup_destination("/tmp/test.txt")

    # Exercise.
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        str(destination_path),
        "local",
    )

    # Verify.
    assert destination_path.exists()
    destination_path.unlink()


def test_upload_asset_via_local_copy_does_not_overwrite(
    temp_file_path,
) -> None:
    # Set up.
    destination_path = setup_destination("/tmp/test.txt")
    # Create a file with a newer timestamp.
    destination_path.write_text("This is a test file that was not overwritten")

    # Exercise.
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        str(destination_path),
        "local",
        expect_failure=True,
    )

    # Verify.
    assert destination_path.exists()
    with open(destination_path, "r") as f:
        assert f.read() == "This is a test file that was not overwritten"
    destination_path.unlink()


def test_upload_asset_via_local_copy_checks_for_space(temp_file_path, caplog) -> None:
    # Set up.
    destination_path = setup_destination("/tmp/test.txt")
    destination_path.unlink(missing_ok=True)
    caplog.set_level(logging.INFO)

    # Exercise.
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        str(destination_path),
        "local",
        additional_args=[
            "--check-space",
            "--check-space-overhead",
            "1000",  # 1000b
        ],
    )

    # Verify caplog.text matches the pattern
    assert any(
        re.search(
            r"Enough space on destination .* Available: \d+b, required: .*",
            message,
        )
        for message in caplog.text.splitlines()
    )

    assert destination_path.exists()
    destination_path.unlink()


def test_upload_asset_via_local_copy_can_overwrite(temp_file_path) -> None:
    # Set up.
    destination_path = setup_destination("/tmp/test.txt")
    destination_path.write_text("This is a test file that will be overwritten")

    # Exercise.
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        str(destination_path),
        "local",
        additional_args=["--overwrite"],
    )

    # Verify.
    assert destination_path.exists()
    contents = ""
    with open(destination_path, "r") as f:
        contents = f.read()

    assert contents.startswith("test-input-file")
    destination_path.unlink()


def test_upload_asset_via_sftp(
    sftp_server, temp_file_path, sftp_creds, sftp_client
) -> None:
    # Set up.
    destination_path = Path("upload/test.txt")

    host_ip = sftp_server.get_container_host_ip()
    host_port = sftp_server.get_exposed_sftp_port()

    temp_file_path.write_bytes(b"test")

    # Exercise.
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        str(destination_path),
        "sftp",
        additional_args=[
            "--host",
            host_ip,
            "--port",
            str(host_port),
            "--username",
            sftp_creds.name,
            "--password",
            sftp_creds.password,
        ],
    )

    # Verify.
    sftp_client.chdir(str(destination_path.parent))
    with tempfile.NamedTemporaryFile() as f:
        sftp_client.get(destination_path.name, f.name)
        f.seek(0)
        assert f.read() == b"test"


def test_upload_asset_via_sftp_checks_for_space(
    sftp_server, temp_file_path, sftp_creds, sftp_client, caplog
) -> None:
    # Set up.
    destination_path = Path("upload/test.txt")

    host_ip = sftp_server.get_container_host_ip()
    host_port = sftp_server.get_exposed_sftp_port()

    temp_file_path.write_bytes(b"test")
    caplog.set_level(logging.INFO)

    # Exercise.
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        str(destination_path),
        "sftp",
        additional_args=[
            "--host",
            host_ip,
            "--port",
            str(host_port),
            "--username",
            sftp_creds.name,
            "--password",
            sftp_creds.password,
            "--check-space",
            "--check-space-overhead",
            "1000",  # 1000b
        ],
    )

    # Verify.
    assert any(
        re.search(
            r"Enough space on destination upload. Available: \d+b, required: 1004b",
            message,
        )
        for message in caplog.text.splitlines()
    )


def test_upload_asset_via_sftp_checks_for_space_and_aborts_if_need_more_than_available(
    sftp_server, temp_file_path, sftp_creds, sftp_client, caplog
) -> None:
    # Set up.
    destination_path = Path("upload/test.txt")
    caplog.set_level(logging.INFO)

    host_ip = sftp_server.get_container_host_ip()
    host_port = sftp_server.get_exposed_sftp_port()

    temp_file_path.write_bytes(b"test")

    # Exercise.
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        str(destination_path),
        "sftp",
        additional_args=[
            "--host",
            host_ip,
            "--port",
            str(host_port),
            "--username",
            sftp_creds.name,
            "--password",
            sftp_creds.password,
            "--check-space",
            # way more than anything available!
            "--check-space-overhead",
            "10000000000000000",
        ],
        expect_failure=True,
    )

    # Verify.
    assert any(
        re.search(
            r"Not enough space on destination upload. Available: \d+b, required: 10000000000000004b",
            message,
        )
        for message in caplog.text.splitlines()
    )


def test_upload_asset_via_sftp_does_not_overwrite(
    sftp_server, temp_file_path, sftp_creds, sftp_client
) -> None:
    # Set up.
    destination_path = Path("upload/test.txt")

    host_ip = sftp_server.get_container_host_ip()
    host_port = sftp_server.get_exposed_sftp_port()

    temp_file_path.write_bytes(b"test")

    # Create a file with a newer timestamp.
    sftp_client.chdir(str(destination_path.parent))

    with tempfile.NamedTemporaryFile() as temp_file:
        temp_file.write(b"This is a newer test file that has not been overwritten")
        temp_file.flush()
        sftp_client.put(Path(temp_file.name), destination_path.name)

    # Exercise.
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        str(destination_path),
        "sftp",
        additional_args=[
            "--host",
            host_ip,
            "--port",
            str(host_port),
            "--username",
            sftp_creds.name,
            "--password",
            sftp_creds.password,
        ],
        expect_failure=True,
    )

    # Verify.
    with tempfile.NamedTemporaryFile() as f:
        sftp_client.get(destination_path.name, f.name)
        f.seek(0)
        assert f.read() == b"This is a newer test file that has not been overwritten"


@pytest.mark.parametrize(
    "args",
    [
        ["--host", None, "--port", 22, "--username", "A", "--password", "B"],
        [
            "--host",
            "host",
            "--port",
            None,
            "--username",
            "A",
            "--password",
            "B",
        ],
        [
            "--host",
            "host",
            "--port",
            22,
            "--username",
            None,
            "--password",
            "B",
        ],
        [
            "--host",
            "host",
            "--port",
            22,
            "--username",
            "A",
            "--password",
            None,
        ],
    ],
)
def test_error_on_missing_sftp_argument(args, temp_file_path, caplog) -> None:
    # Set up.
    destination_path = Path("/tmp/test.txt")
    caplog.set_level(logging.INFO)

    # Exercise.
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        str(destination_path),
        "sftp",
        additional_args=args,
        expect_failure=True,
    )

    # Verify.
    assert (
        "Missing host, port, username or password for SFTP destination" in caplog.text
    )


def test_error_on_unknown_destination_type(temp_file_path) -> None:
    # Set up.
    destination_path = Path("/tmp/test.txt")

    # Exercise.
    with pytest.raises(ValueError) as excinfo:
        asyncio.run(
            upload_asset(
                source_folder=temp_file_path.parent,
                pattern_to_upload=temp_file_path.name,
                destination_file=destination_path,
                destination_type="abcd",
            )
        )

    assert "Unknown destination type abcd" in str(excinfo.value)


def test_upload_asset_via_rclone_local_copy_does_not_overwrite_newer_files_in_update_mode(
    temp_file_path,
) -> None:
    # Set up.
    destination_path = setup_destination("/tmp/test.txt")
    # Create a file with a newer timestamp.
    destination_path.write_text("This is a newer test file.")
    future_mod_time = destination_path.stat().st_mtime + 100
    os.utime(destination_path, (future_mod_time, future_mod_time))

    # Exercise.
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        str(destination_path),
        "rclone",
        additional_args=["--update"],
    )

    # Verify.
    assert destination_path.exists()
    # Verify that the destination file was not overwritten.
    assert destination_path.read_text() == "This is a newer test file."
    destination_path.unlink()


def test_upload_asset_via_rclone_local_copy_does_overwrite_newer_files_in_overwrite_mode(
    temp_file_path,
) -> None:
    # Set up.
    destination_path = setup_destination("/tmp/test.txt")
    # Create a file with a newer timestamp.
    destination_path.write_text("This is a newer test file.")
    future_mod_time = destination_path.stat().st_mtime + 100
    os.utime(destination_path, (future_mod_time, future_mod_time))

    # Exercise.
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        str(destination_path),
        "rclone",
        additional_args=["--overwrite"],
    )

    # Verify.
    assert destination_path.exists()
    # Verify that the destination file was overwritten.
    assert destination_path.read_text() != "This is a newer test file."
    assert destination_path.read_text().startswith("test-input-file")
    destination_path.unlink()


def test_upload_asset_via_rclone_local_copy_does_overwrite_older_files_in_update_mode(
    temp_file_path,
) -> None:
    # Set up.
    destination_path = setup_destination("/tmp/test.txt")
    # Create a file with a newer timestamp.
    destination_path.write_text("This is a test file.")
    past_mod_time = destination_path.stat().st_mtime - 100
    os.utime(destination_path, (past_mod_time, past_mod_time))

    # Exercise.
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        str(destination_path),
        "rclone",
        additional_args=["--update"],
    )

    # Verify.
    assert destination_path.exists()
    # Verify that the destination file was not overwritten.
    assert destination_path.read_text().startswith("test-input-file")
    destination_path.unlink()


def test_upload_asset_via_rclone_local_copy_does_overwrite_older_files_in_overwrite_mode(
    temp_file_path,
) -> None:
    # Set up.
    destination_path = setup_destination("/tmp/test.txt")
    # Create a file with a newer timestamp.
    destination_path.write_text("This is a test file.")
    past_mod_time = destination_path.stat().st_mtime - 100
    os.utime(destination_path, (past_mod_time, past_mod_time))

    # Exercise.
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        str(destination_path),
        "rclone",
        additional_args=["--overwrite"],
    )

    # Verify.
    assert destination_path.exists()
    # Verify that the destination file was overwritten.
    assert destination_path.read_text().startswith("test-input-file")
    destination_path.unlink()


def test_upload_asset_via_rclone_local_copy_does_not_overwrite_older_files_in_normal_mode(
    temp_file_path,
) -> None:
    # Set up.
    destination_path = setup_destination("/tmp/test.txt")
    # Create a file with a newer timestamp.
    message = "This is a test file with a long line of text."

    destination_path.write_text(message)
    past_mod_time = destination_path.stat().st_mtime - 100
    os.utime(destination_path, (past_mod_time, past_mod_time))

    # Exercise.
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        str(destination_path),
        "rclone",
        expect_failure=True,
    )

    # Verify.
    assert destination_path.exists()
    # Verify that the destination file was overwritten.
    assert destination_path.read_text() == message
    destination_path.unlink()


def test_upload_asset_via_rclone_local_copy(temp_file_path) -> None:
    # Set up.
    destination_path = setup_destination("/tmp/test.txt")

    # Exercise.
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        str(destination_path),
        "rclone",
    )

    # Verify.
    assert destination_path.exists()
    destination_path.unlink()


def test_upload_asset_via_rclone_local_copy_into_new_folder(
    temp_file_path,
) -> None:
    # Set up.
    destination_folder = Path("/tmp/upload_test_rclone/")
    destination_path = setup_destination(str(destination_folder / "test.txt"))
    if destination_folder.exists():
        destination_folder.rmdir()

    # Exercise.
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        str(destination_path),
        "rclone",
    )

    # Verify.
    assert destination_path.exists()
    destination_path.unlink()
    if destination_folder.exists():
        destination_folder.rmdir()


def test_upload_asset_via_rclone_memory_with_config_file(
    temp_file_path,
) -> None:
    # Exercise - will check for 0 exit code
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        "in_mem:/not-real/in-memory.txt",
        "rclone",
        additional_args=[
            "--config",
            "tests/inmem_rclone.config",
        ],
    )


def test_failing_to_upload_asset_via_rclone_returns_non_zero(
    temp_file_path,
) -> None:
    # Exercise.
    invoke_upload_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        "/not-real/in-memory.txt",
        "rclone",
        expect_failure=True,
    )


def setup_destination(destination_path: str) -> Path:
    """Helper function to set up the destination path."""
    destination_path = Path(destination_path)
    if destination_path.exists():
        destination_path.unlink()
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    return destination_path
