from pydantic import SecretStr
from prefect_managedfiletransfer import ServerWithPublicKeyAuthBlock
from prefect_managedfiletransfer.ServerWithBasicAuthBlock import (
    ServerWithBasicAuthBlock,
)


def test_server_with_basic_auth_block_is_valid(prefect_db):
    ServerWithBasicAuthBlock.seed_value_for_example()
    block = ServerWithBasicAuthBlock.load("sample-block")
    valid = block.isValid()

    assert valid, "Block should be valid with seeded values"


def test_server_with_public_key_auth_block_is_valid(prefect_db):
    block = ServerWithPublicKeyAuthBlock(
        username="example_user",
        private_key=SecretStr("example_private_key"),
        host="example.com",
        port=22,
    )
    valid = block.is_valid()
    assert valid, "Block should be valid with provided values"
