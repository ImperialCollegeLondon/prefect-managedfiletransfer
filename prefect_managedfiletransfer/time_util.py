from datetime import timedelta
import re

UNITS = {
    "s": "seconds",
    "m": "minutes",
    "h": "hours",
    "d": "days",
    "w": "weeks",
}

# kudos to https://stackoverflow.com/questions/3096860/convert-time-string-expressed-as-numbermhdsw-to-seconds-in-python


def convert_to_seconds(
    duration_text_or_seconds_or_timedelta: str | int | timedelta | None,
) -> int:
    """
    Convert a time string like '1d 2h 30m' or ' to seconds.
    Supports units: seconds (s), minutes (m), hours (h), days (d), weeks (w).
    """

    if duration_text_or_seconds_or_timedelta is None:
        return 0

    # is text already an int?
    if isinstance(duration_text_or_seconds_or_timedelta, int):
        return duration_text_or_seconds_or_timedelta

    # is digit?
    if (
        isinstance(duration_text_or_seconds_or_timedelta, str)
        and duration_text_or_seconds_or_timedelta.isdigit()
    ):
        return int(duration_text_or_seconds_or_timedelta)

    # is text a timedelta?
    if isinstance(duration_text_or_seconds_or_timedelta, timedelta):
        return int(duration_text_or_seconds_or_timedelta.total_seconds())

    duration_text_or_seconds_or_timedelta = str(duration_text_or_seconds_or_timedelta)

    # is text a floaty 123.456 string?
    if re.match(r"^\d+\.\d+$", duration_text_or_seconds_or_timedelta):
        return int(float(duration_text_or_seconds_or_timedelta))

    # if the text contains "month" or "year" parse it manually as we can be rough!
    if re.search(
        r"(month|year|yr)\b",
        duration_text_or_seconds_or_timedelta,
        re.IGNORECASE,
    ):
        months = re.search(
            r"(\d+)\s*month",
            duration_text_or_seconds_or_timedelta,
            re.IGNORECASE,
        )
        years = re.search(
            r"(\d+)\s*(year|yr)",
            duration_text_or_seconds_or_timedelta,
            re.IGNORECASE,
        )

        months = int(months.group(1)) if months else 0
        years = int(years.group(1)) if years else 0

        total_days = years * 365 + months * 30  # rough approximation
        return total_days * 24 * 60 * 60  # convert days to seconds

    # otherwise parse the text
    return int(
        timedelta(
            **{
                UNITS.get(m.group("unit").lower(), "seconds"): float(m.group("val"))
                for m in re.finditer(
                    r"(?P<val>\d+(\.\d+)?)(?P<unit>[smhdw]?)",
                    duration_text_or_seconds_or_timedelta.replace(" ", ""),
                    flags=re.I,
                )
            }
        ).total_seconds()
    )
