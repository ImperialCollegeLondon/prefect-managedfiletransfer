from enum import Enum


class TransferType(str, Enum):
    Copy = "COPY"
    Move = "MOVE"
