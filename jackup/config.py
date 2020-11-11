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


CONFIG = {}

ENV_CONFIG = "JACKUP_CONFIG"

log = logging.getLogger(__name__)


def update(new):
    _config.update(new)
    global CONFIG
    CONFIG = Namespace(**_config)


def _get_config_file():
    # paths to config file, in the ordere they're checked
    paths = [
        os.environ.get(ENV_CONFIG),
        os.path.join(xdg_config_home(), "jackup/jackup.conf"),
        os.path.expanduser("~/.jackup/jackup.conf"),
        os.path.expanduser("~/.jackup"),
    ]

    for p in paths:
        if p and os.path.isfile(p):
            log.debug(f"{p}")
            return p  # use the first valid config file

    # if no config file is found, default to XDG
    return os.path.join(xdg_config_home(), "jackup/jackup.conf")


def _from_file(config_file):
    if config_file and os.path.isfile(config_file):
        with open(os.path.expanduser(config_file), "r") as f:
            return json.load(f)

    return {}


def _from_environment():
    cfg = {}

    # only return keys with valid values
    return {k: v for k, v in cfg.items() if v is not None}


def load():
    config_file = _get_config_file()
    log.debug(f"{config_file=}")

    file_config = _from_file(config_file)
    log.debug(f"{file_config=}")

    env_config = _from_environment()
    log.debug(f"{env_config=}")

    config_path = os.path.dirname(config_file)
    log_path = os.path.join(config_path, "jackup.log")  # TODO: log to /var/log?
    config = {"config_path": config_path, "log_path": log_path}

    config.update(file_config)
    config.update(env_config)
    log.debug(f"{config=}")

    return config
