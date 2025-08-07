from prefect import flow

from prefect_managedfiletransfer.tasks import (
    goodbye_prefect_managedfiletransfer,
    hello_prefect_managedfiletransfer,
)


def test_hello_prefect_managedfiletransfer(prefect_db):
    @flow
    def test_flow():
        return hello_prefect_managedfiletransfer()

    result = test_flow()
    assert result == "Hello, prefect-managedfiletransfer!"


def goodbye_hello_prefect_managedfiletransfer(prefect_db):
    @flow
    def test_flow():
        return goodbye_prefect_managedfiletransfer()

    result = test_flow()
    assert result == "Goodbye, prefect-managedfiletransfer!"
