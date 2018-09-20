import sys
from enum import Enum

class TC(Enum):
    CSI = '\x1B['
    BOLD = CSI + '1m'
    RESET =  CSI + '0m'

    RED = CSI + '31m'
    GREEN = CSI + '32m'
    YELLOW = CSI + '33m'
    BLUE = CSI + '34m'

class VERBOSITY(Enum):
    ERROR = 0
    QUIET = 1
    WARNING = 2
    INFO = 3
    VERBOSE = 4
    DEBUG = 5

def log(string: str, verbosity: VERBOSITY) -> None:
    if verbosity == VERBOSITY.ERROR:
        print(string, file=sys.stderr)
    else:
        print(string, file=sys.stdout)

def info(string: str) -> None:
    log(string, VERBOSITY.INFO)

def success(string: str) -> None:
    log(GREEN(string), VERBOSITY.INFO)

def warning(string: str) -> None:
    log(YELLOW(string), VERBOSITY.WARNING)

def error(string: str) -> None:
    log(RED(string), VERBOSITY.ERROR)

def debug(string: str) -> None:
    log(BLUE(string), VERBOSITY.DEBUG)

def RED(string: str) -> str:
    return "%s%s%s%s" % (TC.BOLD, TC.RED, string, TC.RESET)

def YELLOW(string: str) -> str:
    return "%s%s%s%s" % (TC.BOLD, TC.YELLOW, string, TC.RESET)

def GREEN(string: str) -> str:
    return "%s%s%s%s" % (TC.BOLD, TC.GREEN, string, TC.RESET)

def BLUE(string: str) -> str:
    return "%s%s%s%s" % (TC.BOLD, TC.BLUE, string, TC.RESET)

def BOLD(string: str) -> str:
    return "%s%s%s" % (TC.BOLD, string, TC.RESET)
