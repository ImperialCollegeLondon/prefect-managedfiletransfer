from pydantic import Field
from pathlib import Path
import tempfile
from prefect.blocks.core import Block
from pydantic import SecretStr
import logging

from prefect_managedfiletransfer.constants import CONSTANTS

logger = logging.getLogger(__name__)


class _TemporaryKeyFile:
    def __init__(self, private_key: SecretStr):
        self.private_key = private_key
        self._tempfile = None

    def __enter__(self):
        self._tempfile = tempfile.NamedTemporaryFile("w")
        self._tempfile.write(self.private_key.get_secret_value())
        self._tempfile.flush()

        logging.debug(f"Created temp key file {self._tempfile.name}")

        return self

    def __exit__(self, exc, value, tb):
        result = self._tempfile.__exit__(exc, value, tb)
        self.close()
        return result

    def close(self):
        if self._tempfile is None:
            return
        self._tempfile.close()

    def get_path(self):
        if self._tempfile is None:
            raise ValueError("Temporary key file has not been created yet.")
        return Path(self._tempfile.name)


class ServerWithPublicKeyAuthBlock(Block):
    """
    Block for storing SFTP server details with public key authentication.
    Attributes:
        username: The username for SFTP authentication.
        private_key: The private key for SFTP authentication, stored as a SecretStr.
        host: The hostname or IP address of the SFTP server.
        port: The port number for SFTP, default is 22.

    Example:
        Load a stored value:
        ```python
        from prefect_managedfiletransfer import ServerWithPublicKeyAuthBlock
        block = ServerWithPublicKeyAuthBlock.load("BLOCK_NAME")
        ```
        Creating a block:
        ```python
        from prefect_managedfiletransfer import ServerWithPublicKeyAuthBlock
        block = ServerWithPublicKeyAuthBlock(
            username="example_user",
            private_key=SecretStr("example_private_key"),
            host="example.com",
            port=22,
        )
    """

    _logo_url = CONSTANTS.SERVER_LOGO_URL
    _block_type_name = "Server - Public Key Auth [ManagedFileTransfer]"
    _documentation_url = "https://ImperialCollegeLondon.github.io/prefect-managedfiletransfer/blocks/#prefect-managedfiletransfer.blocks.ServerWithPublicKeyAuthBlock"  # noqa

    username: str = Field(
        title="The username for authentication.",
        description="The username for authentication.",
    )
    private_key: SecretStr = Field(
        title="The private key for authentication.",
        description="The private key for authentication.",
    )
    host: str = Field(
        title="The host of the server.", description="The host of the server."
    )
    port: int = Field(default=22, description="The port of the server.")

    def is_valid(self) -> bool:
        """Checks if the server credentials are available and valid."""

        return (
            self.username
            and self.private_key.get_secret_value()
            and self.host
            and self.port > 0
        )

    def get_temp_key_file(self) -> _TemporaryKeyFile:
        """
        Returns a context manager that provides a temporary file with the private key.
        The file is automatically deleted when the context is exited.
        """
        return _TemporaryKeyFile(self.private_key)

    @classmethod
    def seed_value_for_example(cls):
        """
        Seeds the field, value, so the block can be loaded.
        """
        block = cls(
            username="example_user",
            private_key=SecretStr("example_private_key"),
            host="example.com",
            port=22,
        )
        block.save("sample-block", overwrite=True)
