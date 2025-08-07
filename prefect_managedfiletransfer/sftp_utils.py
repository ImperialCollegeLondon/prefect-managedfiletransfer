import paramiko
import logging

from paramiko import SSHClient
from paramiko.sftp import CMD_EXTENDED, CMD_EXTENDED_REPLY
from io import StringIO
from paramiko import RSAKey, Ed25519Key, ECDSAKey, PKey
from cryptography.hazmat.primitives import (
    serialization as crypto_serialization,
)
from cryptography.hazmat.primitives.asymmetric import ed25519, dsa, rsa, ec

logger = logging.getLogger(__name__)


def connect_to_sftp_remote(
    host, port, username, password, private_key_path=None
) -> tuple[paramiko.Transport, paramiko.SFTPClient]:
    if (
        (host is None)
        or (port is None)
        or (username is None)
        or (password is None and private_key_path is None)
    ):
        logger.critical("Missing host, port, username or password for SFTP destination")
        raise ValueError(
            "Missing host, port, username or password for SFTP destination"
        )

    logger.info(f"Connecting to SFTP server {host}:{port} as {username}")

    transport = paramiko.Transport((host, port))

    if private_key_path:
        try:
            logger.debug("Using key based auth")

            with open(private_key_path, "r") as key_file:
                private_key = from_private_key(key_file, password=password)
            transport.connect(username=username, pkey=private_key)
        except paramiko.SSHException as e:
            logger.critical(f"Failed to connect using private key: {e}")
            raise
    else:
        logger.debug("No private key provided, using password authentication")
        transport.connect(
            username=username,
            password=password,
        )
    sftp = paramiko.SFTPClient.from_transport(transport)
    assert sftp is not None, "SFTP client could not be created"
    return transport, sftp


# thanks to https://stackoverflow.com/questions/60660919/paramiko-ssh-client-is-unable-to-unpack-ed25519-key
def from_private_key(file_obj, password=None) -> PKey:
    """
    Load a private key from a file-like object, where the key type is not known upfront
    Supports RSA, DSA, ECDSA, and Ed25519 keys and returns the correct PKey object needed by Paramiko
    :param file_obj: A file-like object containing the private key.
    :param password: Optional password for encrypted keys.
    :return: An instance of PKey (RSAKey, Ed25519Key, ECDSAKey).
    """
    private_key: PKey | None = None
    file_bytes = bytes(file_obj.read(), "utf-8")
    try:
        key = crypto_serialization.load_ssh_private_key(
            file_bytes,
            password=password,
        )
        file_obj.seek(0)
    except ValueError as e_ssh:
        logger.info(f"Tried and failed to load key as an SSH private key: {e_ssh}")
        # Fallback to PEM format if SSH format fails
        file_obj.seek(0)
        logger.debug("Trying to load as a PEM private key")
        try:
            key = crypto_serialization.load_pem_private_key(
                file_bytes,
                password=password,
            )
        except ValueError as e_pem:
            logger.info(f"Tried and failed to load key as a PEM private key: {e_pem}")
            # Fallback to DER format if PEM format fails
            raise ValueError(
                f"Failed to load private key from file. Ensure it is in a supported format (OpenSSH or PEM, with RSA or Ed25519).\nError for PEM: {e_pem}\nError for SSH: {e_ssh}"
            )
        if password:
            encryption_algorithm = crypto_serialization.BestAvailableEncryption(
                password
            )
        else:
            encryption_algorithm = crypto_serialization.NoEncryption()
        file_obj = StringIO(
            key.private_bytes(
                crypto_serialization.Encoding.PEM,
                crypto_serialization.PrivateFormat.OpenSSH,
                encryption_algorithm,
            ).decode("utf-8")
        )
    if isinstance(key, rsa.RSAPrivateKey):
        private_key = RSAKey.from_private_key(file_obj, password)
        logger.debug(f"Loaded RSA private key from file {file_obj.name}")
    elif isinstance(key, ed25519.Ed25519PrivateKey):
        private_key = Ed25519Key.from_private_key(file_obj, password)
        logger.debug(f"Loaded Ed25519 private key from file {file_obj.name}")
    elif isinstance(key, ec.EllipticCurvePrivateKey):
        private_key = ECDSAKey.from_private_key(file_obj, password)
        logger.debug(f"Loaded ECDSA private key from file {file_obj.name}")
    elif isinstance(key, dsa.DSAPrivateKey):
        logger.warning(
            "DSA keys are not recommended as they are old and insecure, consider using RSA or Ed25519 instead"
        )
        try:
            from paramiko import DSSKey  # noqa: F401

            private_key = DSSKey.from_private_key(file_obj, password)
        except ImportError as ex:
            logger.error(f"Failed to import DSSKey: {ex}")
            logger.error(
                "DSSKey is not supported by Paramiko anymore - if you really need this use an old version of paramiko at your own risk"
            )
            raise ValueError("DSSKey is not supported by Paramiko", ex)
    else:
        raise TypeError("Unsupported key type: {}".format(type(key)))
    return private_key


def connect_to_sftp_remote_using_ssh(
    host, port, username, password, private_key_path=None
) -> tuple[paramiko.SSHClient, paramiko.SFTPClient]:
    if (
        (host is None)
        or (port is None)
        or (username is None)
        or (password is None and private_key_path is None)
    ):
        logger.critical("Missing host, port, username or password for SFTP destination")
        raise ValueError(
            "Missing host, port, username or password for SFTP destination"
        )

    logger.info(f"Connecting to SSH server {host}:{port} as {username}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    if private_key_path:
        try:
            logger.debug("Using key based auth")
            with open(private_key_path, "r") as key_file:
                private_key = from_private_key(key_file, password=password)
            client.connect(
                hostname=host,
                port=port,
                username=username,
                pkey=private_key,
                allow_agent=False,
            )
        except paramiko.SSHException as e:
            logger.critical(f"Failed to connect using private key: {e}")
            raise
    else:
        logger.debug("No private key provided, using password authentication")
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            allow_agent=False,
        )
    sftp = client.open_sftp()
    assert sftp is not None, "SFTP client could not be created"
    return client, sftp


def try_get_remote_disk_space(ssh_client: SSHClient, path) -> int:
    """
    Try to get the available disk space on the remote server using df over SSH.
    Returns the available space in bytes or -1 if it fails.
    """

    free_bytes = -1

    if not ssh_client:
        logger.error("SSH client is not connected")
        return -1

    try:
        logger.debug(
            f"Trying to get remote disk space using SFTP non std command statvfs@openssh.com for: {path}"
        )
        sftp_client = ssh_client.open_sftp()
        sftp_client._adjust_cwd(path)
        t, msg = sftp_client._request(CMD_EXTENDED, "statvfs@openssh.com", path)
    except Exception as e:
        logger.warning(f"Failed to get remote disk space using SFTP: {e}")

    if t != CMD_EXTENDED_REPLY:
        logger.error(f"Expected extended reply response, got {t}")
    else:
        block_size = msg.get_int64()
        fundamental_block_size = msg.get_int64()  # noqa: F841
        blocks = msg.get_int64()  # noqa: F841
        free_blocks = msg.get_int64()
        available_blocks = msg.get_int64()  # noqa: F841
        file_inodes = msg.get_int64()  # noqa: F841
        free_file_inodes = msg.get_int64()  # noqa: F841
        available_file_inodes = msg.get_int64()  # noqa: F841
        sid = msg.get_int64()  # noqa: F841
        flags = msg.get_int64()  # noqa: F841
        name_max = msg.get_int64()  # noqa: F841

        free_bytes = block_size * free_blocks

        logger.debug(
            f"Successfully parsed remote disk space using statvfs: {free_bytes} bytes available at {path}"
        )

    if free_bytes >= 0:
        return free_bytes

    # if SFTP failed, try using SSH command
    logger.debug("Falling back to SSH command to get remote disk space")

    try:
        stdin, stdout, stderr = ssh_client.exec_command(
            f"df -B1 --output=avail '{path}' | tail -1"
        )
        output = stdout.read().decode().strip()
        if not output.isdigit():
            logger.error(f"Failed to parse disk space output: {output}")
            return -1
        else:
            free_bytes = int(output)
            logger.debug(f"Remote disk space available at {path}: {free_bytes} bytes")
            return free_bytes
    finally:
        return -1
