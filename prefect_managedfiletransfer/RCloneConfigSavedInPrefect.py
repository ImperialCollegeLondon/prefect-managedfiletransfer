from prefect_managedfiletransfer import RCloneConfigFileBlock
from prefect_managedfiletransfer.RCloneConfig import RCloneConfig


class RCloneConfigSavedInPrefect(RCloneConfig):
    """
    RCloneDynamicConfig that uses a Prefect block to store the rclone config file contents. Is saved after sucessful uploads to update the token when it is refreshed
    """

    def __init__(self, block: RCloneConfigFileBlock):
        super().__init__(remote_name=block.remote_name)
        self._block = block

    def get_config(self):
        return self._block.config_file_contents

    async def update_config(self, config_contents: str):
        self._block.config_file_contents = config_contents
        await self._block.save(overwrite=True)
