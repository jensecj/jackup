import os
import logging

from types import SimpleNamespace as Namespace

from xdg import xdg_config_home

LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(message)s"},
        "standard": {
            "format": "%(asctime)s [%(levelname)-7s] %(name)s:%(lineno)s: %(message)s"
        },
        "colored": {
            "()": "colorlog.ColoredFormatter",
            "format": "%(asctime)s %(log_color)s[%(levelname)-7s]%(reset)s %(white)s%(name)s:%(lineno)s%(reset)s: %(message)s",
            "log_colors": {
                "DEBUG": "cyan",
                "INFO": "white",
                "WARNING": "yellow",
                "ERROR": "red",
            },
        },
    },
    "handlers": {
        "default": {
            "formatter": "simple",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "extended": {
            "formatter": "colored",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {},
    "root": {
        "handlers": ["default"],
        "level": "INFO",
        "propagate": False,
    },
}


config_path = os.path.expanduser("~/.config/jackup/")
log_path = os.path.join(config_path, "jackup.log")  # TODO: log to /var/log?

_config = {"config_path": config_path, "log_path": log_path}
CONFIG = Namespace(**_config)


log = logging.getLogger(__name__)


def update(new):
    _config.update(new)
    global CONFIG
    CONFIG = Namespace(**_config)

