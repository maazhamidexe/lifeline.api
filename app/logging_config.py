import logging
import os


def configure_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format=log_format,
        force=True,
    )

    # Keep uvicorn and app logs aligned.
    logging.getLogger("uvicorn").setLevel(getattr(logging, log_level, logging.INFO))
    logging.getLogger("uvicorn.error").setLevel(getattr(logging, log_level, logging.INFO))
    logging.getLogger("uvicorn.access").setLevel(getattr(logging, log_level, logging.INFO))
