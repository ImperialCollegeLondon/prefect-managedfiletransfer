import logging
import os
from pathlib import Path
import sys
import tempfile
import pytest
from prefect_managedfiletransfer.main import app
from testcontainers.sftp import SFTPContainer, SFTPUser
import paramiko
from typing import Generator
from prefect.testing.utilities import prefect_test_harness

from TestCliRunner import TestCliRunner

default_sftp_username = "basic"
default_sftp_password = "password"

# quieten some loggers for dependencies when run in tests with debug
print("\n[conftest.py] Setting loggers to INFO level for matplotlib and PIL...\n")
logging.getLogger("paramiko").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)
logging.getLogger("httpcore.connection").setLevel(logging.INFO)
logging.getLogger("httpcore.http11").setLevel(logging.INFO)
logging.getLogger("asyncio:selector_events.py").setLevel(logging.INFO)


@pytest.fixture(scope="session", autouse=False)
def prefect_db():
    """
    Sets up test harness for temporary DB during test runs.
    """
    os.environ["PREFECT_LOGGING_EXTRA_LOGGERS"] = "prefect_managedfiletransfer"
    with prefect_test_harness():
        yield


@pytest.fixture()
def runner(caplog) -> TestCliRunner:
    runner = TestCliRunner(app, caplog)
    caplog.set_level(logging.INFO)
    return runner


@pytest.fixture(autouse=False)
def sftp_creds() -> SFTPUser:
    return SFTPUser(name=default_sftp_username, password=default_sftp_password)


@pytest.fixture(autouse=False)
def sftp_server(sftp_creds: SFTPUser) -> Generator[SFTPContainer, None, None]:
    """Fixture to start an SFTP server in a container."""

    if sys.platform.startswith("win"):
        pytest.skip("skipping SFTP tests on winodws - needs docker!")

    users = [sftp_creds]

    with SFTPContainer(users=users) as sftp:
        host_ip = sftp.get_container_host_ip()
        host_port = sftp.get_exposed_sftp_port()

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            host_ip,
            host_port,
            username=sftp_creds.name,
            password=sftp_creds.password,
            # needed as vscode exposes SSH_AUTH_SOCK, see https://github.com/paramiko/paramiko/issues/2124
            allow_agent=False,
        )

        yield sftp


@pytest.fixture(autouse=False)
def sftp_client(
    sftp_server, sftp_creds: SFTPUser
) -> Generator[paramiko.SFTPClient, None, None]:
    """Fixture to create an SFTP client connected to the SFTP server."""

    host_ip = sftp_server.get_container_host_ip()
    host_port = sftp_server.get_exposed_sftp_port()

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        host_ip,
        host_port,
        username=sftp_creds.name,
        password=sftp_creds.password,
        allow_agent=False,
    )

    sftp_client = ssh.open_sftp()
    yield sftp_client
    sftp_client.close()


@pytest.fixture(autouse=False)
def temp_file_path() -> Generator[Path, None, None]:
    """Fixture to create a temporary file for testing."""

    with tempfile.NamedTemporaryFile() as temp_file:
        # Write some content to the temporary file
        temp_file.write(b"test-input-file")
        temp_file.flush()  # Ensure the content is written to disk
        yield Path(temp_file.name)


@pytest.fixture(autouse=False)
def temp_folder_path() -> Generator[Path, None, None]:
    """Fixture to create a temporary folder for testing."""

    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)
