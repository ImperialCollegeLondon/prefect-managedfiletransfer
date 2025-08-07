import subprocess
import logging
import threading
import tempfile
import os
from typing import List, Union, Optional


def invoke_rclone(
    command: Union[List[str], str],
    config_file_contents: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
    capture_std_output: bool = False,
) -> tuple[int, Optional[str], Optional[List[str]], Optional[Exception]]:
    """
    Executes an rclone command and streams the output to the Python logger at INFO level in real-time.
    Optionally creates a temporary config file with the provided content.

    Args:
        command: Either a list of command arguments or a string with the full command
        config_file_contents: Optional content for the rclone config file. If provided, a temporary
                       config file will be created with this content and used for the command.

    Returns:
        tuple: (return_code, config_content_after, StdOutput lines, Exception)
            - return_code: The exit code from the rclone process
            - config_content_after: Content of the config file after command execution
              (useful for retrieving tokens that might have been updated by rclone)

    Example:
        invoke_rclone(
            'rclone lsf "my_remote_name:Calibration test data/example"',
            config_file_contents='[my_remote_name]\ntype = onedrive\ntoken = {"access_token":"test"}'
        )
    """

    # Convert string command to list if needed
    if isinstance(command, str):
        import shlex

        cmd = shlex.split(command)
    else:
        cmd = command.copy()  # Create a copy to avoid modifying the original

    # Set up logger
    if logger is None:
        logger = logging.getLogger(__name__)

    temp_config_file = None
    config_content_after = None
    rclone_config_argument = "--config"
    stdout_thread = None
    stderr_thread = None
    return_code = 0
    ex: Exception | None = None
    lines: list[str] | None = [] if capture_std_output else None

    if config_file_contents is not None and rclone_config_argument in cmd:
        raise ValueError(
            f"cannot pass config_file_contents and have config file argument '{rclone_config_argument}' in command"
        )

    try:
        # Create temporary config file if content is provided
        if config_file_contents is not None:
            temp_config_file = tempfile.NamedTemporaryFile(
                mode="w+", delete=False, suffix=".conf"
            )
            temp_config_path = temp_config_file.name
            logger.debug(f"Creating temporary config file at {temp_config_path}")

            # Write the config content to the file
            temp_config_file.write(config_file_contents)
            temp_config_file.flush()
            temp_config_file.close()

            # For list commands, find the index of '--config' if it exists
            config_idx = -1
            for i, arg in enumerate(cmd):
                if arg == rclone_config_argument and i < len(cmd) - 1:
                    config_idx = i
                    break

            if config_idx >= 0:
                # Replace the existing config path
                cmd[config_idx + 1] = temp_config_path
                logger.warning(f"Overridden config path to {temp_config_path}")
            else:
                # Insert --config after the first element (which should be 'rclone')
                cmd.insert(1, rclone_config_argument)
                cmd.insert(2, temp_config_path)

        if (
            "-vv" not in cmd
            and logging.getLogger().getEffectiveLevel() == logging.DEBUG
            and "lsf" not in cmd
        ):
            cmd.insert(1, "-vv")
            logger.debug("Added -vv to command for verbose output")

        if (
            "-v" not in cmd
            and logging.getLogger().getEffectiveLevel() == logging.INFO
            and "lsf" not in cmd
        ):
            cmd.insert(1, "-v")
            logger.debug("Added -v to command for verbose output")

        if not cmd or (
            not cmd[0].endswith("rclone") and not cmd[0].endswith("rclone.exe")
        ):
            logger.error("Command must start with 'rclone' or /path/to/rclone")
            return (
                1,
                None,
                None,
                ValueError("Command must start with 'rclone' or /path/to/rclone"),
            )

        # ensure all paths are strings
        cmd = [str(arg) for arg in cmd]

        logger.info(f"Running rclone command: {' '.join(cmd)}")

        # Start the subprocess with pipes for stdout and stderr
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,  # Unbuffered
        )

        # Create threads to handle stdout and stderr streams simultaneously
        stdout_thread = threading.Thread(
            target=_log_stream, args=(process.stdout, "stdout", logger, lines)
        )

        error_lines: list[str] = []
        stderr_thread = threading.Thread(
            target=_log_stream,
            args=(process.stderr, "stderr", logger, error_lines),
        )

        # Start the threads
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()

        # Wait for the process to complete
        return_code = process.wait()

        # Wait for the logging to complete
        stdout_thread.join()
        stderr_thread.join()

        logger.info(f"rclone completed with return code: {return_code}")

        if return_code != 0 and any(
            "directory not found" in line for line in error_lines
        ):
            ex = FileNotFoundError(
                "rclone command failed with 'directory not found' error. "
                "Please check the remote path and ensure it exists."
            )

        # Read the config file content after the command execution if it was created
        if temp_config_file is not None:
            with open(temp_config_path, "r") as f:
                config_content_after = f.read()

    except Exception as e:
        logger.error(f"Failed to execute rclone command: {e}. \n{e.__traceback__}")
        return_code = 1
        ex = e

    finally:
        # Clean up the temporary config file
        if temp_config_file is not None:
            try:
                os.unlink(temp_config_path)
                logger.info(f"Removed temporary config file: {temp_config_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary config file: {e}")

        # make sure we dispose of the threads
        if stdout_thread and stdout_thread.is_alive():
            stdout_thread.join()
        if stderr_thread and stderr_thread.is_alive():
            stderr_thread.join()

    return return_code, config_content_after, lines, ex


def _log_stream(stream, prefix, logger, captured_lines=None):
    """Helper function to log a stream line by line in real-time."""
    for line in iter(stream.readline, ""):
        line = line.strip()
        if line:
            if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
                logger.debug(f"[{prefix}] {line}")
            else:
                logger.info(line)

            if captured_lines is not None:
                captured_lines.append(line)
