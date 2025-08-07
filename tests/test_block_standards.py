import pytest
from prefect.testing.standard_test_suites import BlockStandardTestSuite

import prefect_managedfiletransfer


def find_module_blocks():
    return [
        prefect_managedfiletransfer.ServerWithBasicAuthBlock,
        prefect_managedfiletransfer.ServerWithPublicKeyAuthBlock,
        prefect_managedfiletransfer.RCloneConfigFileBlock,
    ]


@pytest.mark.parametrize("block", find_module_blocks())
class TestAllBlocksAdhereToStandards(BlockStandardTestSuite):
    @pytest.fixture
    def block(self, block):
        print(f"Testing block: {block.__name__}")
        return block
