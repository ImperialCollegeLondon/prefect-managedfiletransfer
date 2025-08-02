import pytest
from prefect.blocks.core import Block
from prefect.testing.standard_test_suites import BlockStandardTestSuite
from prefect.utilities.dispatch import get_registry_for_type
from prefect.utilities.importtools import to_qualified_name

# block_registry = get_registry_for_type(Block) or {}

# blocks_under_test = [
#     block
#     for block in block_registry.values()
#     if to_qualified_name(block).startswith("prefect_managedfiletransfer")
# ]

# @pytest.mark.parametrize(
#     "block", sorted(blocks_under_test, key=lambda x: x.get_block_type_slug())
# )


def find_module_blocks():
    blocks = get_registry_for_type(Block)
    module_blocks = [
        block
        for block in blocks.values()
        if to_qualified_name(block).startswith("prefect_managedfiletransfer")
    ]
    return module_blocks


@pytest.mark.parametrize("block", find_module_blocks())
class TestAllBlocksAdhereToStandards(BlockStandardTestSuite):
    @pytest.fixture
    def block(self, block):
        print(f"Testing block: {block.__name__}")
        return block
