import logging

logger = logging.getLogger(__name__)


class Doctor:
    @staticmethod
    def hello_world():
        logger.debug("I'm really chatty")
        logger.info("Hello, I'm the doctor")
        logger.warning("You ought to be careful")
        logger.error("This is very wrong")
