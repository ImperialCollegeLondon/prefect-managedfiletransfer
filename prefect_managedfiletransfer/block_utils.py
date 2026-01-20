from prefect import get_run_logger
from prefect.filesystems import LocalFileSystem

from prefect_managedfiletransfer.RCloneConfigFileBlock import RCloneConfigFileBlock
from prefect_managedfiletransfer.ServerWithBasicAuthBlock import (
    ServerWithBasicAuthBlock,
)
from prefect_managedfiletransfer.ServerWithPublicKeyAuthBlock import (
    ServerWithPublicKeyAuthBlock,
)


async def try_fetch_block(
    block_name: str,
) -> (
    ServerWithBasicAuthBlock
    | ServerWithPublicKeyAuthBlock
    | LocalFileSystem
    | RCloneConfigFileBlock
    | None
):
    """
    Attempts to load a block by name from Prefect. Tries each block type until one succeeds.

    Args:
        block_name: The name of the block to load.

    Returns:
        The loaded block, or None if no block with that name was found.
    """
    logger = get_run_logger()
    result = None

    logger.info(f"Trying loading block details from block with key {block_name}")

    try:
        result = await ServerWithBasicAuthBlock.aload(block_name)
        logger.debug(f"Loaded SFTP details from block with key {block_name}")
    except ValueError:
        logger.debug(f"Failed to load ServerWithBasicAuthBlock with key {block_name}")

    try:
        result = await ServerWithPublicKeyAuthBlock.aload(block_name)
        logger.debug(f"Loaded ServerWithPublicKeyAuthBlock with key {block_name}")
    except ValueError:
        logger.debug(
            f"Failed to load ServerWithPublicKeyAuthBlock with key {block_name}"
        )

    try:
        result = await LocalFileSystem.aload(block_name)
        logger.debug(f"Loaded LocalFileSystem with key {block_name}")
    except ValueError:
        logger.debug(f"Failed to load LocalFileSystem with key {block_name}")

    try:
        result = await RCloneConfigFileBlock.aload(block_name)
        logger.debug(f"Loaded RCloneConfigFileBlock with key {block_name}")
    except ValueError:
        logger.debug(f"Failed to load RCloneConfigFileBlock with key {block_name}")

    return result
