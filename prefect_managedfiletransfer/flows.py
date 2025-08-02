"""This is an example flows module"""
from prefect import flow

from prefect_managedfiletransfer.blocks import ServerWithBasicAuthBlock
from prefect_managedfiletransfer.tasks import (
    goodbye_prefect_managedfiletransfer,
    hello_prefect_managedfiletransfer,
)


@flow
def hello_and_goodbye():
    """
    Sample flow that says hello and goodbye!
    """
    ServerWithBasicAuthBlock.seed_value_for_example()
    block = ServerWithBasicAuthBlock.load("sample-block")

    print(hello_prefect_managedfiletransfer())
    print(f"The block's contents: {block.host}:{block.port} as {block.username}")
    print(goodbye_prefect_managedfiletransfer())

    return "Done"


if __name__ == "__main__":
    hello_and_goodbye()
