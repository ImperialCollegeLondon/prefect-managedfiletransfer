from pathlib import Path

from prefect_managedfiletransfer.RemoteConnectionType import RemoteConnectionType


class PathUtil:
    @staticmethod
    def resolve_path(
        path_type: RemoteConnectionType,
        basepath: Path | str | None,
        path: Path | str,
    ) -> Path:
        if path_type == RemoteConnectionType.LOCAL:
            remote_source_path = PathUtil._local_resolve_path(
                basepath, path, validate=True
            )
        else:
            remote_source_path = PathUtil._resolve_remote_path(
                basepath, path, validate=True
            )

        return remote_source_path

    @staticmethod
    def _local_resolve_path(
        basepath: str | Path | None, path: str | Path, validate: bool = False
    ) -> Path:
        # Only resolve the base path at runtime, default to the current directory
        resolved_basepath = (
            Path(basepath).expanduser().resolve() if basepath else Path(".").resolve()
        )

        # Determine the path to access relative to the base path, ensuring that paths
        # outside of the base path are off limits
        if path is None:
            return resolved_basepath

        resolved_path: Path = Path(path).expanduser()

        if not resolved_path.is_absolute():
            resolved_path = resolved_basepath / resolved_path
        else:
            resolved_path = resolved_path.resolve()

        if validate:
            if resolved_basepath not in resolved_path.parents and (
                resolved_basepath != resolved_path
            ):
                raise ValueError(
                    f"Provided path {resolved_path} is outside of the base path {resolved_basepath}."
                )
        return resolved_path

    @staticmethod
    def _resolve_remote_path(
        basepath: str | Path | None, path: str | Path, validate: bool = False
    ) -> Path:
        if path is None and basepath is None:
            return Path(".")
        elif path is None:
            return basepath

        path = str(path).strip()
        basepath = str(basepath).strip() if basepath else ""

        if not path.startswith("/") and len(basepath) > 0:
            resolved_path = f"{basepath.rstrip('/')}/{path}"
        else:
            resolved_path = path

        if validate:
            if (
                len(basepath) > 0
                and Path(basepath) not in Path(resolved_path).parents
                and basepath != resolved_path
            ):
                raise ValueError(
                    f"Provided path {resolved_path} is outside of the base path {basepath}."
                )
            if len(basepath) > 0 and ".." in resolved_path:
                raise ValueError(
                    f"Provided path {resolved_path} contains '..' so cannot be validated to be within basepath. Remove basepath if .. is required"
                )
        return Path(resolved_path)
