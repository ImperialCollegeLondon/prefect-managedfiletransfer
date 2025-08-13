from prefect_managedfiletransfer import (
    RCloneConfigFileBlock,
    ServerWithPublicKeyAuthBlock,
)
from prefect_managedfiletransfer.ServerWithBasicAuthBlock import (
    ServerWithBasicAuthBlock,
)


def test_server_with_basic_auth_block_is_valid(prefect_db):
    ServerWithBasicAuthBlock.seed_value_for_example()
    block = ServerWithBasicAuthBlock.load("sample-block")
    valid = block.isValid()

    assert valid, "Block should be valid with seeded values"


def test_server_with_public_key_auth_block_is_valid(prefect_db):
    ServerWithPublicKeyAuthBlock.seed_value_for_example()
    block = ServerWithPublicKeyAuthBlock.load("sample-block")

    valid = block.is_valid()
    assert valid, "Block should be valid with provided values"


def test_rclone_block_is_valid(prefect_db):
    RCloneConfigFileBlock.seed_value_for_example()
    block = RCloneConfigFileBlock.load("sample-block")

    assert block.remote_name == "my_sharepoint"
