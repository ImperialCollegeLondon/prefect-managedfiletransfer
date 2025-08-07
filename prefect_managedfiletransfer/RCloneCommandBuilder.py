import importlib
import logging
from pathlib import Path
import platform
import subprocess
import importlib.resources
from prefect_managedfiletransfer.RCloneConfig import RCloneConfig

logger = logging.getLogger(__name__)


class RCloneCommandBuilder:
    def __init__(
        self,
        rclone_config_file: Path | None = None,
        rclone_config: RCloneConfig | None = None,
    ):
        self.rclone_config = rclone_config
        self.rclone_config_file = rclone_config_file

        self._rclone_executable = "rclone"
        packaged_folder = Path(
            str(
                importlib.resources.files("prefect_managedfiletransfer").joinpath(
                    "rclone"
                )
            )
        )
        packaged_executable = packaged_folder / self._rclone_executable

        if platform.system() == "Windows":
            self._rclone_executable = "rclone.exe"
            packaged_executable = packaged_folder / self._rclone_executable
            logger.debug(
                f"rclone windows packaged executable is at {packaged_executable}"
            )
        elif platform.system() == "Darwin":
            packaged_executable = packaged_folder / "osx" / self._rclone_executable
            logger.debug(
                f"rclone macOS packaged executable is at {packaged_executable}"
            )
        else:
            logger.debug(
                f"rclone linux packaged executable is at {packaged_executable}"
            )

        # Check if rclone is available on the system path
        try:
            subprocess.run(
                f"{self._rclone_executable} version",
                shell=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.debug(
                f"Using rclone executable on PATH: '{self._rclone_executable}'"
            )
        except subprocess.CalledProcessError:
            logger.warning(
                "rclone is not available on PATH - using packaged version at "
                + str(packaged_executable)
            )
            self._rclone_executable = str(packaged_executable)

        try:
            subprocess.run(
                [self._rclone_executable, "version"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            logger.critical(
                f"rclone executable {self._rclone_executable} is not available or not executable"
            )
            raise FileNotFoundError(
                f"rclone executable {self._rclone_executable} is not available or not executable"
            )

        self.rclone_command = [self._rclone_executable]

        if rclone_config_file is not None and rclone_config is not None:
            raise ValueError(
                "rclone_config_file and rclone_config_contents cannot be used at the same time"
            )

        if rclone_config_file is not None and not rclone_config_file.exists():
            logger.critical(f"rclone config file {rclone_config_file} does not exist")
            raise FileNotFoundError(
                f"rclone config file {rclone_config_file} does not exist"
            )

        if rclone_config_file is not None and rclone_config_file.exists():
            logger.info(f"Using rclone config file {rclone_config_file.absolute()}")
            self.rclone_command.insert(1, "--config")
            self.rclone_command.insert(2, str(rclone_config_file.absolute()))
        elif rclone_config is not None:
            logger.info(f"Using rclone config for remote {rclone_config.remote_name}")
        else:
            logger.info(
                "No rclone config file or rclone config object provided, using default rclone config, probably [HOME]/.config/rclone/rclone.conf"
            )

    def uploadTo(
        self,
        source_file,
        destination_file: Path,
        update_only_if_newer_mode=False,
    ) -> "RCloneCommandBuilder":
        rclone_remote_pathstr = str(destination_file).lstrip()

        rclone_remote_pathstr = self._apply_remote_prefix(rclone_remote_pathstr)

        return self.copyTo(
            source_file, update_only_if_newer_mode, rclone_remote_pathstr
        )

    def downloadTo(
        self,
        source_file,
        destination_file,
        update_only_if_newer_mode=False,
    ) -> "RCloneCommandBuilder":
        rclone_remote_pathstr = str(source_file).lstrip()

        rclone_remote_pathstr = self._apply_remote_prefix(rclone_remote_pathstr)

        return self.copyTo(
            rclone_remote_pathstr, update_only_if_newer_mode, destination_file
        )

    def deleteFile(
        self,
        remote_file,
    ) -> "RCloneCommandBuilder":
        rclone_remote_pathstr = str(remote_file).lstrip()

        rclone_remote_pathstr = self._apply_remote_prefix(rclone_remote_pathstr)
        logger.info(f"Using rclone to delete {str(remote_file)}")

        self.rclone_command += ["deletefile", rclone_remote_pathstr]

        return self

    def copyTo(self, source_file, update_only_if_newer_mode, rclone_remote_pathstr):
        if update_only_if_newer_mode:
            logger.info(
                "Using rclone with --update flag to skip files that are newer on the destination"
            )
            self.rclone_command.append("--update")

        logger.info(
            f"Using rclone to copy {str(source_file)} to {rclone_remote_pathstr}"
        )

        self.rclone_command += [
            "copyto",
            str(source_file),
            rclone_remote_pathstr,
            "--check-first",  # try and catch issues before starting upload
            "--checksum",  # be thorough and check checksums
            "--max-duration",
            "30m",  # don't let the upload take forever, this is a safety net
        ]

        return self

    def _apply_remote_prefix(self, rclone_remote_pathstr):
        if self.rclone_config is not None and not rclone_remote_pathstr.startswith(
            f"{self.rclone_config.remote_name}:"
        ):
            logger.debug(
                f"Destination {rclone_remote_pathstr} does not start with {self.rclone_config.remote_name}:, adding it"
            )
            rclone_remote_pathstr = (
                f"{self.rclone_config.remote_name}:{rclone_remote_pathstr}"
            )

        return rclone_remote_pathstr

    def lsf(
        self, remote_folder: Path, pattern_to_match: str | None = None
    ) -> "RCloneCommandBuilder":
        rclone_remote_pathstr = str(remote_folder).rstrip(
            "/"
        )  # Ensure no trailing slash
        rclone_remote_pathstr = self._apply_remote_prefix(rclone_remote_pathstr)

        self.rclone_command += [
            "lsf",
            "--files-only",
            "--format",
            "tsp",  # time, size, path
            rclone_remote_pathstr,
        ]

        if pattern_to_match:
            logger.info(
                f"Using rclone to list files in {rclone_remote_pathstr} matching pattern {pattern_to_match}"
            )
            self.rclone_command += ["--include", pattern_to_match]

        return self

    def build(self, custom_executable_path: str | Path = None) -> list[str]:
        """
        Build the rclone command as a list of strings.
        """

        if custom_executable_path:
            logger.info(f"Using custom rclone executable at {custom_executable_path}")
            self._rclone_executable = custom_executable_path

        self.rclone_command[0] = str(self._rclone_executable)

        return self.rclone_command.copy()
