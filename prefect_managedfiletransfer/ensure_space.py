import logging

logger = logging.getLogger(__name__)


def ensure_space(
    source_size, available_space, check_for_space_overhead, destination_folder
):
    if available_space is None or available_space < 0:
        logger.warning(
            f"Available space is None or negative on destination {destination_folder}, assuming no space available"
        )
        raise RuntimeError(
            f"Unable to determine available space on destination {destination_folder}"
        )

    if available_space < (source_size + check_for_space_overhead):
        logger.critical(
            f"Not enough space on destination {destination_folder}. Available: {available_space}b, required: {source_size + check_for_space_overhead}b"
        )
        raise RuntimeError(
            f"Not enough space on destination {destination_folder}. Available: {available_space}b, required: {source_size + check_for_space_overhead}b"
        )
    else:
        logger.info(
            f"Enough space on destination {destination_folder}. Available: {available_space}b, required: {source_size + check_for_space_overhead}b"
        )
