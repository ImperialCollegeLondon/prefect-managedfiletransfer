"""This is an example blocks module"""

from prefect.blocks.core import Block
from pydantic import VERSION as PYDANTIC_VERSION

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field
else:
    from pydantic import Field


class ManagedfiletransferBlock(Block):
    """
    A sample block that holds a value.

    Attributes:
        value (str): The value to store.

    Example:
        Load a stored value:
        ```python
        from prefect_managedfiletransfer import ManagedfiletransferBlock
        block = ManagedfiletransferBlock.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "managedfiletransfer"
    # replace this with a relevant logo; defaults to Prefect logo
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/08yCE6xpJMX9Kjl5VArDS/c2ede674c20f90b9b6edeab71feffac9/prefect-200x200.png?h=250"  # noqa
    _documentation_url = "https://ImperialCollegeLondon.github.io/prefect-managedfiletransfer/blocks/#prefect-managedfiletransfer.blocks.ManagedfiletransferBlock"  # noqa

    value: str = Field("The default value", description="The value to store.")

    @classmethod
    def seed_value_for_example(cls):
        """
        Seeds the field, value, so the block can be loaded.
        """
        block = cls(value="A sample value")
        block.save("sample-block", overwrite=True)
