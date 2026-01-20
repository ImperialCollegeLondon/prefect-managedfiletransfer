#!/usr/bin/env python
import logging
import os
from pathlib import Path

import pytest

from typer.testing import CliRunner

from prefect_managedfiletransfer.main import app

runner = CliRunner()


def invoke_list_command(
    remote_folder,
    pattern,
    args: list[str] = ["--remote-type", "local"],
    expect_failure=False,
):
    result = runner.invoke(
        app,
        [
            "list",
            "--remote-folder",
            remote_folder,
            "--pattern-to-match",
            pattern,
        ]
        + args,
    )

    print(result.stderr)
    print(result.stdout)

    # Verify.
    if expect_failure:
        assert result.exit_code != 0
    else:
        if result.exception:
            raise result.exception
        assert result.exit_code == 0

    return result


def test_list_remote_asset_via_local(temp_folder_path) -> None:
    # Set up.
    remote_path = temp_folder_path / "test.txt"
    remote_path.write_text("test content")

    # Exercise.
    result = invoke_list_command(
        str(temp_folder_path), "test*", ["--remote-type", "local"]
    )

    # Verify.
    assert str(remote_path) in result.output


def test_list_remote_asset_via_local_using_min_age_ignores_files_too_new(
    temp_folder_path,
) -> None:
    # Set up.
    remote_path = temp_folder_path / "test.txt"
    remote_path.write_text("test content")

    # Exercise.
    result = invoke_list_command(
        str(temp_folder_path),
        "test*",
        ["--remote-type", "local", "--min-age", "1m"],
        expect_failure=True,
    )

    # Verify.
    assert str(remote_path) not in result.output


def test_list_remote_asset_via_local_using_max_age_ignores_files_too_old(
    temp_folder_path,
) -> None:
    # Set up.
    remote_path = temp_folder_path / "test.txt"
    remote_path.write_text("test content")
    # Set the modification time to 2 minutes ago
    file_mtime = remote_path.stat().st_mtime - 120
    os.utime(remote_path, (file_mtime, file_mtime))

    # Exercise.
    result = invoke_list_command(
        str(temp_folder_path),
        "test*",
        ["--remote-type", "local", "--max-age", "1m"],
        expect_failure=True,
    )

    # Verify.
    assert str(remote_path) not in result.output


def test_list_remote_asset_via_local_using_take_ignores_files_beyond_limit(
    temp_folder_path,
) -> None:
    # Set up.
    for i in range(1, 6):  # 5 files
        (temp_folder_path / f"test_{i}.txt").write_text(f"test content {i}")

    # Exercise.
    result = invoke_list_command(
        str(temp_folder_path),
        "test*",
        ["--remote-type", "local", "--take", "1"],
    )

    # Verify.
    assert str(temp_folder_path / "test_1.txt") in result.output
    assert str(temp_folder_path / "test_2.txt") not in result.output
    assert str(temp_folder_path / "test_3.txt") not in result.output
    assert str(temp_folder_path / "test_4.txt") not in result.output
    assert str(temp_folder_path / "test_5.txt") not in result.output


def test_list_remote_asset_via_local_using_skip_ignores_files_before_limit(
    temp_folder_path,
) -> None:
    # Set up.
    for i in range(1, 6):  # 5 files
        (temp_folder_path / f"test_{i}.txt").write_text(f"test content {i}")

    # Exercise.
    result = invoke_list_command(
        str(temp_folder_path),
        "test*",
        ["--remote-type", "local", "--skip", "1"],
    )

    # Verify.
    assert str(temp_folder_path / "test_1.txt") not in result.output
    assert str(temp_folder_path / "test_2.txt") in result.output
    assert str(temp_folder_path / "test_3.txt") in result.output
    assert str(temp_folder_path / "test_4.txt") in result.output
    assert str(temp_folder_path / "test_5.txt") in result.output


def test_list_asset_via_sftp(
    sftp_server, temp_file_path, sftp_creds, sftp_client
) -> None:
    # Set up.
    destination_path = Path("upload/test.txt")

    host_ip = sftp_server.get_container_host_ip()
    host_port = sftp_server.get_exposed_sftp_port()

    temp_file_path.write_bytes(b"test")

    sftp_client.chdir(destination_path.parent.as_posix())
    sftp_client.put(temp_file_path.as_posix(), destination_path.name)

    # Exercise.
    result = invoke_list_command(
        remote_folder="upload",
        pattern="*.txt",
        args=[
            "--remote-type",
            "sftp",
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
    assert str(destination_path) in result.output


def test_list_asset_via_sftp_with_zero_files(
    sftp_server, temp_file_path, sftp_creds, sftp_client, caplog
) -> None:
    # Set up.
    host_ip = sftp_server.get_container_host_ip()
    host_port = sftp_server.get_exposed_sftp_port()
    caplog.set_level(logging.INFO)

    # Exercise.
    result = invoke_list_command(
        remote_folder="upload",
        pattern="not-a-file",
        args=[
            "--remote-type",
            "sftp",
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
    assert str("Zero files found") in caplog.text
    assert result.exit_code == 3


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
    result = invoke_list_command(
        "upload",
        "*.txt",
        [
            "--remote-type",
            "sftp",
        ]
        + args,
        expect_failure=True,
    )

    # Verify.
    assert result.exit_code != 0
    assert (
        "Missing host, port, username or password for SFTP destination" in caplog.text
    )


def test_list_remote_asset_via_rclone(temp_folder_path) -> None:
    # Set up.
    remote_path = temp_folder_path / "test.txt"
    remote_path.write_text("test content")

    # Exercise.
    result = invoke_list_command(
        str(temp_folder_path), "*.txt", ["--remote-type", "rclone"]
    )

    # Verify.
    assert str(remote_path) in result.output


def test_list_asset_via_rclone_memory_with_config_file_and_zero_files_returns_nothing(
    caplog,
) -> None:
    # Exercise.
    caplog.set_level(logging.INFO)
    result = invoke_list_command(
        "in_mem:/not-real/",
        "in-memory.txt",
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
    assert "Zero files found" in caplog.text
