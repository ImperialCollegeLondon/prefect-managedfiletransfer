import logging
from typing import Union

# blocks
from prefect_managedfiletransfer.ServerWithBasicAuthBlock import (
    ServerWithBasicAuthBlock,
)  # noqa
from prefect_managedfiletransfer.ServerWithPublicKeyAuthBlock import (
    ServerWithPublicKeyAuthBlock,
)  # noqa
from prefect_managedfiletransfer.RCloneConfigFileBlock import RCloneConfigFileBlock  # noqa

from prefect.filesystems import LocalFileSystem as PrefectLocalFileSystem  # noqa

TransferBlockType = Union[
    ServerWithBasicAuthBlock,
    ServerWithPublicKeyAuthBlock,
    PrefectLocalFileSystem,
    RCloneConfigFileBlock,
]

# flows
from prefect_managedfiletransfer.transfer_files_flow import transfer_files_flow  # noqa
from prefect_managedfiletransfer.upload_file_flow import upload_file_flow  # noqa
from prefect_managedfiletransfer.delete_files_flow import delete_files_flow  # noqa

# tasks
from prefect_managedfiletransfer.upload_file_task import upload_file_task  # noqa
from prefect_managedfiletransfer.download_file_task import download_file_task  # noqa
from prefect_managedfiletransfer.list_remote_files_task import list_remote_files_task  # noqa
from prefect_managedfiletransfer.delete_file_task import delete_file_task  # noqa

# models
from prefect_managedfiletransfer.RemoteConnectionType import RemoteConnectionType  # noqa
from prefect_managedfiletransfer.RemoteAsset import RemoteAsset  # noqa
from prefect_managedfiletransfer.FileMatcher import FileMatcher  # noqa
from prefect_managedfiletransfer.FileToFolderMapping import FileToFolderMapping  # noqa
from prefect_managedfiletransfer.TransferType import TransferType  # noqa

# by default emit logs at the INFO level
logging.getLogger("prefect_managedfiletransfer").setLevel(logging.INFO)


__all__ = [
    "ServerWithBasicAuthBlock",
    "ServerWithPublicKeyAuthBlock",
    "RCloneConfigFileBlock",
    "transfer_files_flow",
    "upload_file_flow",
    "delete_files_flow",
    "upload_file_task",
    "download_file_task",
    "list_remote_files_task",
    "delete_file_task",
    "RemoteConnectionType",
    "RemoteAsset",
    "FileMatcher",
    "FileToFolderMapping",
    "TransferType",
]
