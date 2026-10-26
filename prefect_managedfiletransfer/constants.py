class CONSTANTS:
    SKIPPED_STATE_NAME = "Skipped"
    SERVER_LOGO_URL = "https://raw.githubusercontent.com/ImperialCollegeLondon/prefect-managedfiletransfer/docs/img/managed-file-transfer.png"
    ONE_GIGABYTE = 1024 * 1024 * 1024

    class ENV_VAR_NAMES:
        PMFTUPLOAD_USERNAME = "PMFTUPLOAD_USERNAME"
        PMFTUPLOAD_PASSWORD = "PMFTUPLOAD_PASSWORD"

    class FLOW_NAMES:
        UPLOAD_FILE = "upload-file"
        TRANSFER_FILES = "transfer-files"
        UNPACK_FILES = "unpack-files"
        DELETE_FILES = "delete-files"

    class DEPLOYMENT_NAMES:
        UPLOAD_FILE = "upload_file"
        TRANSFER_FILES = "transfer_files"
        UNPACK_FILES = "unpack_files"
        DELETE_FILES = "delete_files"
