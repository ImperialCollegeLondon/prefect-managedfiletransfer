from typing import Any, Dict, Optional
from prefect.blocks.core import Block
from pydantic import Field, SecretStr, model_validator

from prefect_managedfiletransfer.constants import CONSTANTS


class ServerWithBasicAuthBlock(Block):
    """
    A connection to a remote server with basic authentication.

    Attributes:
        username (str): The username for authentication.
        password (SecretStr): The password for authentication.
        host (str): The host of the server.
        port (int): The port of the server.

    Example:
        Load a stored value:
        ```python
        from prefect_managedfiletransfer import ServerWithBasicAuthBlock
        block = ServerWithBasicAuthBlock.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "server_with_basic_auth"
    _logo_url = CONSTANTS.SERVER_LOGO_URL
    _documentation_url = "https://ImperialCollegeLondon.github.io/prefect-managedfiletransfer/blocks/#prefect-managedfiletransfer.blocks.ServerWithBasicAuthBlock"  # noqa

    username: str = Field(
        title="The username for authentication.",
        description="The username for authentication.",
    )
    password: Optional[SecretStr] = Field(
        default=None,
        title="The password for authentication.",
        description="The password for authentication.",
    )
    host: str = Field(
        title="The host of the server.", description="The host of the server."
    )
    port: int = Field(default=22, description="The port of the server.")

    @classmethod
    def seed_value_for_example(cls):
        """
        Seeds the field, value, so the block can be loaded.
        """
        block = cls(
            username="example_user",
            password=SecretStr("example_password"),
            host="example.com",
            port=22,
        )
        block.save("sample-block", overwrite=True)

    def isValid(self) -> bool:
        """Checks if the server credentials are available and valid."""
        return (
            self.username
            and self.password.get_secret_value()
            and self.host
            and self.port > 0
        )

    @model_validator(mode="before")
    @classmethod
    def check_valid(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Checks that either a connection string or account URL is provided, not both.
        """

        if not values.get("username") is not None or not values.get("password"):
            raise ValueError("Must provide a username and password.")
        if not values.get("host") or not values.get("port") or values["port"] <= 0:
            raise ValueError("Must provide a valid host and port.")
        return values
