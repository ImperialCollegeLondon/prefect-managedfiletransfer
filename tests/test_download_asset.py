#!/usr/bin/env python
"""Tests for `download_asset` package."""
# pylint: disable=redefined-outer-name

import logging
import os
import re
from pathlib import Path

import pytest

from typer.testing import CliRunner

from prefect_managedfiletransfer.main import app

runner = CliRunner()


def invoke_download_command(
    remote_folder,
    pattern,
    destination_folder: Path = Path("/tmp/"),
    args: list[str] = ["--remote-type", "local"],
    expect_failure=False,
):
    result = runner.invoke(
        app,
        [
            "download",
            "--remote-folder",
            remote_folder,
            "--pattern-to-match",
            pattern,
            "--destination-folder",
            str(destination_folder),
        ]
        + args,
    )

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


def test_download_asset_via_local_copy(temp_file_path) -> None:
    # Set up.
    destination_path = Path(".")
    expected_file = destination_path / temp_file_path.name

    # Exercise.
    invoke_download_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        destination_path,
        ["--remote-type", "local"],
    )

    assert expected_file.exists()
    expected_file.unlink()


def test_download_asset_via_sftp(
    sftp_server, temp_file_path, sftp_creds, sftp_client
) -> None:
    # Set up.
    source_path = Path("upload/") / "example.cdf"
    destination_path = Path("/tmp")
    temp_file_path.write_bytes(b"test")
    expected_file = destination_path / source_path.name
    expected_file.unlink(missing_ok=True)  # Ensure the file does not exist
    host_ip = sftp_server.get_container_host_ip()
    host_port = sftp_server.get_exposed_sftp_port()
    # upload file for us to test download
    sftp_client.chdir(source_path.parent.as_posix())
    sftp_client.put(
        localpath=temp_file_path.absolute().as_posix(),
        remotepath=source_path.name,
    )

    # Exercise.
    invoke_download_command(
        str(source_path.parent),
        source_path.name,
        destination_path,
        [
            "--remote-type",
            "sftp",
            "--host",
            host_ip,
            "--port",
            host_port,
            "--username",
            sftp_creds.name,
            "--password",
            sftp_creds.password,
        ],
    )

    # assert file exists and has correct length
    assert expected_file.exists()
    assert expected_file.stat().st_size == temp_file_path.stat().st_size
    expected_file.unlink()


def test_download_asset_via_sftp_checks_for_space_on_destination(
    sftp_server, temp_file_path, sftp_creds, sftp_client, caplog
) -> None:
    # Set up.
    source_path = Path("upload/") / "example.cdf"
    destination_path = Path("/tmp")
    temp_file_path.write_bytes(b"test")
    expected_file = destination_path / source_path.name
    expected_file.unlink(missing_ok=True)  # Ensure the file does not exist
    host_ip = sftp_server.get_container_host_ip()
    host_port = sftp_server.get_exposed_sftp_port()
    # upload file for us to test download
    sftp_client.chdir(source_path.parent.as_posix())
    sftp_client.put(
        localpath=temp_file_path.absolute().as_posix(),
        remotepath=source_path.name,
    )
    caplog.set_level(logging.INFO)

    # Exercise.
    invoke_download_command(
        str(source_path.parent),
        source_path.name,
        destination_path,
        [
            "--remote-type",
            "sftp",
            "--host",
            host_ip,
            "--port",
            host_port,
            "--username",
            sftp_creds.name,
            "--password",
            sftp_creds.password,
            "--check-space",
            "--check-space-overhead",
            "1000",  # 1KB overhead
        ],
    )

    regexPattern = r"Enough space on destination /tmp. Available: \d+b, required: 1004b"
    # validate caplog.text matches the pattern
    assert any(re.search(regexPattern, message) for message in caplog.text.splitlines())


def test_download_asset_via_sftp_without_overwrite_when_file_exists_does_error(
    sftp_server, temp_file_path, sftp_creds, sftp_client
) -> None:
    # Set up.
    source_path = Path("upload/") / "example.cdf"
    destination_path = Path("/tmp")
    temp_file_path.write_bytes(b"test")
    expected_file = destination_path / source_path.name
    host_ip = sftp_server.get_container_host_ip()
    host_port = sftp_server.get_exposed_sftp_port()
    # upload file for us to test download
    sftp_client.chdir(source_path.parent.as_posix())
    sftp_client.put(
        localpath=temp_file_path.absolute().as_posix(),
        remotepath=source_path.name,
    )

    expected_file.touch()

    # Exercise.
    result = invoke_download_command(
        str(source_path.parent),
        source_path.name,
        destination_path,
        [
            "--remote-type",
            "sftp",
            "--host",
            host_ip,
            "--port",
            host_port,
            "--username",
            sftp_creds.name,
            "--password",
            sftp_creds.password,
        ],
        expect_failure=True,
    )

    # assert file exists and has correct length
    assert result.exit_code == 2


def test_download_asset_via_sftp_with_overwrite_when_file_exists_does_download(
    sftp_server, temp_file_path, sftp_creds, sftp_client
) -> None:
    # Set up.
    source_path = Path("upload/") / "example.cdf"
    destination_path = Path("/tmp")
    temp_file_path.write_bytes(b"test")
    expected_file = destination_path / source_path.name
    host_ip = sftp_server.get_container_host_ip()
    host_port = sftp_server.get_exposed_sftp_port()
    # upload file for us to test download
    sftp_client.chdir(source_path.parent.as_posix())
    sftp_client.put(
        localpath=temp_file_path.absolute().as_posix(),
        remotepath=source_path.name,
    )

    expected_file.touch()

    # Exercise.
    invoke_download_command(
        str(source_path.parent),
        source_path.name,
        destination_path,
        [
            "--remote-type",
            "sftp",
            "--host",
            host_ip,
            "--port",
            host_port,
            "--username",
            sftp_creds.name,
            "--password",
            sftp_creds.password,
            "--overwrite",
        ],
    )

    # assert file exists and has correct length
    assert expected_file.exists()
    assert expected_file.stat().st_size == temp_file_path.stat().st_size
    expected_file.unlink()
    assert (
        sftp_client.stat(source_path.name).st_size == temp_file_path.stat().st_size
    ), "Should not have modified the source file unless in move mode"


def test_download_asset_via_sftp_with_overwrite_and_move_when_file_exists_does_download_and_delete_source(
    sftp_server, temp_file_path, sftp_creds, sftp_client
) -> None:
    # Set up.
    source_path = Path("upload/") / "example.cdf"
    destination_path = Path("/tmp")
    temp_file_path.write_bytes(b"test")
    expected_file = destination_path / source_path.name
    host_ip = sftp_server.get_container_host_ip()
    host_port = sftp_server.get_exposed_sftp_port()
    # upload file for us to test download
    sftp_client.chdir(source_path.parent.as_posix())
    sftp_client.put(
        localpath=temp_file_path.absolute().as_posix(),
        remotepath=source_path.name,
    )

    expected_file.touch()

    # Exercise.
    invoke_download_command(
        str(source_path.parent),
        source_path.name,
        destination_path,
        [
            "--remote-type",
            "sftp",
            "--host",
            host_ip,
            "--port",
            host_port,
            "--username",
            sftp_creds.name,
            "--password",
            sftp_creds.password,
            "--overwrite",
            "--move",
        ],
    )

    # assert file exists and has correct length
    assert expected_file.exists()
    assert expected_file.stat().st_size == temp_file_path.stat().st_size
    expected_file.unlink()
    with pytest.raises(FileNotFoundError) as exception:
        sftp_client.stat(source_path.name)
    assert exception is not None


def test_download_asset_via_rclone_local_copy_does_overwrite_older_files_in_update_mode(
    temp_file_path,
) -> None:
    # Set up.
    destination_path = Path("/tmp/dest/") / temp_file_path.name
    os.makedirs(destination_path.parent, exist_ok=True)
    # Create a file with a newer timestamp.
    destination_path.write_text("This should be overwritten.")
    past_mod_time = destination_path.stat().st_mtime - 500
    os.utime(destination_path, (past_mod_time, past_mod_time))
    # Exercise.

    invoke_download_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        destination_path.parent,
        ["--remote-type", "rclone", "--update"],
    )

    # Verify.
    assert destination_path.exists()
    # Verify that the destination file was not overwritten.
    assert destination_path.read_text().startswith("test-input-file")

    destination_path.unlink()


def test_download_asset_via_rclone_local_copy(temp_file_path) -> None:
    # Set up.
    destination_path = Path("/tmp/dest/") / temp_file_path.name
    os.makedirs(destination_path.parent, exist_ok=True)

    # Exercise.
    invoke_download_command(
        str(temp_file_path.parent),
        temp_file_path.name,
        destination_path.parent,
        ["--remote-type", "rclone"],
    )

    # verify
    assert destination_path.exists()
    destination_path.unlink()


def test_download_asset_via_rclone_memory_with_config_file_for_missing_file_errors(
    temp_file_path,
) -> None:
    destination_path = Path("/tmp/dest/") / temp_file_path.name
    os.makedirs(destination_path.parent, exist_ok=True)

    # Exercise.
    result = invoke_download_command(
        "in_mem:/not-real",
        "not-a-file.txt",
        str(destination_path.parent),
        [
            "--remote-type",
            "rclone",
            "--config",
            "tests/inmem_rclone.config",
        ],
        expect_failure=True,
    )

    # Verify.
    assert result.exit_code == 3
