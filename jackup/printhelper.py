class TC:
    CSI = '\x1B['
    BOLD = CSI + '1m'
    RESET =  CSI + '0m'

    RED = CSI + '31m'
    GREEN = CSI + '32m'
    YELLOW = CSI + '33m'
    BLUE = CSI + '34m'

def success(string):
    print(TC.BOLD + TC.GREEN + string + TC.RESET)

def error(string):
    print(TC.BOLD + TC.RED + string + TC.RESET)

def warning(string):
    print(TC.BOLD + TC.YELLOW + string + TC.RESET)

def RED(string):
    return TC.BOLD + TC.RED + string + TC.RESET;

def YELLOW(string):
    return TC.BOLD + TC.YELLOW + string + TC.RESET;

def GREEN(string):
    return TC.BOLD + TC.GREEN + string + TC.RESET;

def BOLD(string):
    return TC.BOLD + string + TC.RESET;
