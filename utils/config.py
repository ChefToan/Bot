# utils/config.py
import os
from dotenv import load_dotenv
import coc
import logging
import colorlog
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Load environment variables
load_dotenv()


class Config:
    # Discord configuration
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

    # Clash of Clans configuration
    COC_EMAIL = os.getenv('COC_EMAIL')
    COC_PASSWORD = os.getenv('COC_PASSWORD')

    # Logging configuration
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = '[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s'
    LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    LOG_DIR = Path('logs')
    LOG_FILE = LOG_DIR / 'bot.log'
    MAX_BYTES = 32 * 1024 * 1024  # 32 MB
    BACKUP_COUNT = 5


def setup_logging():
    """Set up logging configuration"""
    # Create logs directory if it doesn't exist
    Config.LOG_DIR.mkdir(exist_ok=True)

    # Remove all existing handlers
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)

    # Create console handler with colored output
    console_handler = colorlog.StreamHandler()
    console_handler.setFormatter(colorlog.ColoredFormatter(
        '%(log_color)s[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s%(reset)s',
        datefmt=Config.LOG_DATE_FORMAT,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        },
        secondary_log_colors={
            'message': {
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red'
            }
        }
    ))

    # Create file handler
    file_handler = RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=Config.MAX_BYTES,
        backupCount=Config.BACKUP_COUNT
    )
    file_handler.setFormatter(logging.Formatter(Config.LOG_FORMAT, Config.LOG_DATE_FORMAT))

    # Configure root logger
    root.setLevel(Config.LOG_LEVEL)
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # Set levels for specific loggers while keeping their output
    logging.getLogger('discord').setLevel(logging.INFO)
    logging.getLogger('coc').setLevel(logging.INFO)

    # Create and return bot logger
    logger = logging.getLogger('bot')
    logger.setLevel(Config.LOG_LEVEL)

    return logger


async def setup_coc_client():
    """Set up and authenticate COC client"""
    try:
        client = coc.Client(key_names="Discord Bot", key_count=1)
        await client.login(
            email=Config.COC_EMAIL,
            password=Config.COC_PASSWORD
        )
        return client
    except Exception as e:
        logging.getLogger('bot').error(f"Failed to initialize COC client: {e}")
        raise