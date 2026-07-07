from io import StringIO

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import dsa, rsa
from paramiko import RSAKey

from prefect_managedfiletransfer.sftp_utils import from_private_key


def test_from_private_key_loads_rsa_key():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    loaded_key = from_private_key(StringIO(private_key_pem))

    assert isinstance(loaded_key, RSAKey)


def test_from_private_key_rejects_dsa_keys():
    private_key = dsa.generate_private_key(key_size=1024)
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    with pytest.raises(ValueError, match="DSA private keys are not supported"):
        from_private_key(StringIO(private_key_pem))
