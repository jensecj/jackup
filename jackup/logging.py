import sys

class TC:
    CSI = '\x1B['
    BOLD = CSI + '1m'
    RESET =  CSI + '0m'

    RED = CSI + '31m'
    GREEN = CSI + '32m'
    YELLOW = CSI + '33m'
    BLUE = CSI + '34m'

class VERBOSITY:
    ERROR = 0
    QUIET = 1
    WARNING = 2
    INFO = 3
    VERBOSE = 4
    DEBUG = 5

# given a verbosity level, print all messages at, or below that level
def log(string, verbosity):
    if verbosity == VERBOSITY.ERROR:
        print(string, file=sys.stderr)
        return

    print(string, file=sys.stdout)

def info(string):
    log(string, VERBOSITY.INFO)

def success(string):
    log(GREEN(string), VERBOSITY.INFO)

def warning(string):
    log(YELLOW(string), VERBOSITY.WARNING)

def error(string):
    log(RED(string), VERBOSITY.ERROR)

def debug(string):
    log(BLUE(string), VERBOSITY.DEBUG)

def RED(string):
    return TC.BOLD + TC.RED + string + TC.RESET;

def YELLOW(string):
    return TC.BOLD + TC.YELLOW + string + TC.RESET;

def GREEN(string):
    return TC.BOLD + TC.GREEN + string + TC.RESET;

def BLUE(string):
    return TC.BOLD + TC.BLUE + string + TC.RESET;

def BOLD(string):
    return TC.BOLD + string + TC.RESET;
