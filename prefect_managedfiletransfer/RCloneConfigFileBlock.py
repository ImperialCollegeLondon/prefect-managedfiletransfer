from pydantic import Field
from prefect.blocks.core import Block


class RCloneConfigFileBlock(Block):
    """
    Block for storing RClone configuration file contents.
    This block is used to store the contents of an RClone configuration file, which can be used to configure RClone for file transfers.
    The block is updated with tokends when they are refreshed, allowing for dynamic updates to the RClone configuration.

    Generate a config locally with `rclone config create my_sharepoint onedrive` like below, then save the contents in a block with remote_name=my_sharepoint,config_file_contents=
    [my_sharepoint]
    type = onedrive
    token = {"access_token":"...","token_type":"Bearer","refresh_token":"...","expiry":"2000-00-00T00:00:00.000000000Z"}
    drive_id = b!-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    drive_type = documentLibrary

    Attributes:
        remote_name (str): The name of the remote connection.
        config_file_contents (str): The contents of the RClone configuration file.

    Example:
        Load a stored value:
        ```python
        from prefect_managedfiletransfer import RCloneConfigFileBlock
        block = RCloneConfigFileBlock.load("BLOCK_NAME")
        ```

        Creating a block:
        ```python
        from prefect_managedfiletransfer import RCloneConfigFileBlock
        block = RCloneConfigFileBlock(
            remote_name="my_sharepoint",
            config_file_contents="..."
        )
        block.save("my_sharepoint_block", overwrite=True)
        ```
    """

    _block_type_name = "RClone Remote Config File [ManagedFileTransfer]"
    _logo_url = "https://github.com/rclone/rclone/blob/master/graphics/logo/logo_symbol/logo_symbol_color_64px.png?raw=true"
    _documentation_url = "https://ImperialCollegeLondon.github.io/prefect-managedfiletransfer/blocks/#prefect-managedfiletransfer.blocks.RCloneConfigFileBlock"  # noqa

    remote_name: str = Field(
        title="Remote Name",
        description="The name of the remote connection in the RClone configuration.",
    )
    config_file_contents: str = Field(
        title="Config File Contents",
        description="The contents of the RClone configuration file.",
    )

    @classmethod
    def seed_value_for_example(cls):
        """
        Seeds the field, value, so the block can be loaded.
        """
        block = cls(
            remote_name="my_sharepoint",
            config_file_contents="""
                                [my_sharepoint]
                                type = onedrive
                                token = {"access_token":"...","token_type":"Bearer","refresh_token":"...","expiry":"2000-00-00T00:00:00.000000000Z"}
                                drive_id = b!-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
                                drive_type = documentLibrary
                                """,
        )

        block.save("sample-block", overwrite=True)
