import logging
from logging.handlers import RotatingFileHandler, QueueHandler, QueueListener
from queue import Queue

# Create a queue for logging
__log_queue = Queue()


# Configure the root logger
def setup_logger():
    # Create a parent logger
    _logger = logging.getLogger()
    _logger.setLevel(logging.DEBUG)


    # Create a handler for the queue
    queue_handler = QueueHandler(__log_queue)


    # Create a formatter that includes the logger name (module name)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create handlers (e.g., console and file)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        "app.log", maxBytes=1024 * 1024, backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)


    # Create a QueueListener to process logs in a separate thread
    _listener = QueueListener(__log_queue, console_handler, file_handler)


    # Add the handlers to the logger
    _logger.addHandler(queue_handler)
    _listener.start()

    return _logger, listener

# Create a logger and listener
logger, listener = setup_logger()