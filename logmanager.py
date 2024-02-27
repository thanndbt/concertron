import logging

class LogManager:
    def __init__(self, module, log_file='concertron.log'):
        self.log_file = log_file
        self.logger = self._setup_logger(module)

    def _setup_logger(self, module):
        logger = logging.getLogger(module)
        logger.setLevel(logging.DEBUG)

        # Create file handler which logs messages to a file
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)

        # Create console handler with a higher log level
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add the handlers to the logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def exception(self, message):
        self.logger.exception(message)

    def debug(self, message):
        self.logger.debug(message)
