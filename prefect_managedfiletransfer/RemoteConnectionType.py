from enum import Enum


class RemoteConnectionType(Enum):
    LOCAL = "local"
    SFTP = "sftp"
    RCLONE = "rclone"
