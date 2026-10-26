from pathlib import Path

import pytest
from PIL import Image
from prefect.testing.standard_test_suites import BlockStandardTestSuite

import prefect_managedfiletransfer
from prefect_managedfiletransfer.constants import CONSTANTS


@pytest.mark.parametrize(
    "block",
    [
        prefect_managedfiletransfer.ServerWithBasicAuthBlock,
        prefect_managedfiletransfer.ServerWithPublicKeyAuthBlock,
    ],
)
def test_server_blocks_use_docs_logo(block):
    assert str(block._logo_url) == CONSTANTS.SERVER_LOGO_URL
    assert CONSTANTS.SERVER_LOGO_URL == (
        "https://raw.githubusercontent.com/ImperialCollegeLondon/"
        "prefect-managedfiletransfer/docs/img/managed-file-transfer.png"
    )


def test_docs_source_preserves_server_logo():
    logo_path = Path(__file__).resolve().parents[1] / "docs/img/managed-file-transfer.png"
    with Image.open(logo_path) as logo:
        assert logo.format == "PNG"
        assert logo.size == (512, 512)
        logo.verify()


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
