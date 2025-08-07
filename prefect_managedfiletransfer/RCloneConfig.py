class RCloneConfig:
    def __init__(self, remote_name: str):
        self.remote_name = remote_name
        self._config_contents: str

    def get_config(self):
        return self._config_contents

    async def update_config(self, config_contents: str):
        self._config_contents = config_contents
