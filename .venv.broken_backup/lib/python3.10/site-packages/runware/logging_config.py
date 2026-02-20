import logging


def add_console_handler(logger, formatter):
    # does it already exist? if so, return None
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            return None
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def configure_logging(log_level=logging.DEBUG):
    # Create a formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)
    add_console_handler(logger, formatter)

    asyncio_logger = logging.getLogger("asyncio")
    asyncio_logger.setLevel(log_level)
    add_console_handler(asyncio_logger, formatter)

    websockets_logger = logging.getLogger("websockets")
    websockets_logger.setLevel(log_level)
    websockets_logger.propagate = False
    add_console_handler(websockets_logger, formatter)
