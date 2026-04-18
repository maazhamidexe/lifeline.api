import logging


def configure_logging() -> None:
    log_level = "INFO"
    log_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format=log_format,
        force=True,
    )

    # Keep uvicorn and app logs aligned.
    logging.getLogger("uvicorn").setLevel(getattr(logging, log_level, logging.INFO))
    logging.getLogger("uvicorn.error").setLevel(getattr(logging, log_level, logging.INFO))
    logging.getLogger("uvicorn.access").setLevel(getattr(logging, log_level, logging.INFO))
