from pydantic import SecretStr


def get_password_value(password: str | SecretStr | None) -> str | None:
    """
    Extract the actual password value from either a plain string or a SecretStr.

    Args:
        password: The password value, which can be a str, SecretStr, or None.

    Returns:
        The password as a plain string, or None if the input was None.
    """
    if password is None:
        return None
    if isinstance(password, SecretStr):
        return password.get_secret_value()
    return password
