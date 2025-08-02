from prefect_managedfiletransfer.blocks import ServerWithBasicAuthBlock


def test_block_is_valid():

    ServerWithBasicAuthBlock.seed_value_for_example()
    block = ServerWithBasicAuthBlock.load("sample-block")
    valid = block.isValid()

    assert valid, "Block should be valid with seeded values"
