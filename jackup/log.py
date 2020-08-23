import sys
from datetime import datetime
from enum import Enum, IntEnum

from jackup.config import CONFIG


class TC(Enum):
    CSI = "\x1B["
    BOLD = CSI + "1m"
    RESET = CSI + "0m"

    RED = CSI + "31m"
    GREEN = CSI + "32m"
    YELLOW = CSI + "33m"
    BLUE = CSI + "34m"


class LEVEL(IntEnum):
    ERROR = 0
    WARNING = 1
    INFO = 2
    DEBUG = 3


LOG_LEVEL = LEVEL.INFO


def set_level(level: LEVEL) -> None:
    global LOG_LEVEL
    LOG_LEVEL = level


# TODO: write logs to config.log_path
def log(string: str, level: LEVEL) -> None:
    # augment log-messages with timestamp and logging level
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logstr = f"{now} [{level.name}]: {string}"

    # always write all messages to the log file
    with open(CONFIG.log_path, "a") as f:
        f.write(logstr + "\n")

    # dont print messages if LOG_LEVEL is too low
    if LOG_LEVEL < level:
        return

    # if debugging, use the augmented message
    if LOG_LEVEL == LEVEL.DEBUG:
        string = logstr

    if level == LEVEL.ERROR:
        print(string, file=sys.stderr)
    else:
        print(string, file=sys.stdout)


def info(string: str) -> None:
    log(string, LEVEL.INFO)


def success(string: str) -> None:
    log(GREEN(string), LEVEL.INFO)


def warning(string: str) -> None:
    log(YELLOW(string), LEVEL.WARNING)


def error(string: str) -> None:
    log(RED(string), LEVEL.ERROR)


def debug(string: str) -> None:
    log(BLUE(string), LEVEL.DEBUG)


def RED(string: str) -> str:
    return "%s%s%s%s" % (TC.BOLD.value, TC.RED.value, string, TC.RESET.value)


def YELLOW(string: str) -> str:
    return "%s%s%s%s" % (TC.BOLD.value, TC.YELLOW.value, string, TC.RESET.value)


def GREEN(string: str) -> str:
    return "%s%s%s%s" % (TC.BOLD.value, TC.GREEN.value, string, TC.RESET.value)


def BLUE(string: str) -> str:
    return "%s%s%s%s" % (TC.BOLD.value, TC.BLUE.value, string, TC.RESET.value)


def BOLD(string: str) -> str:
    return "%s%s%s" % (TC.BOLD.value, string, TC.RESET.value)
