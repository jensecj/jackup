import os
import sys
import argparse
from pathlib import Path

from jackup.core import add, remove, list, sync

def version(config):
    print('Jackup version 0.2 - alpha')

def main():
    # setup the parser for commandline usage
    parser = argparse.ArgumentParser(description="Jackup: Simple synchronization.")
    subparsers = parser.add_subparsers()

    add_parser = subparsers.add_parser("add", help="Add a slave to repository")
    add_parser.add_argument("profile", help="profile to add slaves to")
    add_parser.add_argument("name", help="name of the slave to add to the repository")
    add_parser.add_argument("source", help="source to sync from, can be a directory of file")
    add_parser.add_argument("destination", help="destination to sync to, can be a directory or file")
    add_parser.add_argument('--ssh', nargs='?', dest="port", type=int, const=22, default=0, help="if the slave in on a remote machine")
    add_parser.set_defaults(func=add)

    remove_parser = subparsers.add_parser("remove", aliases=['rm'], help="Remove a slave from repository")
    remove_parser.add_argument("name", help="name of the slave to remove")
    remove_parser.set_defaults(func=remove)

    list_parser = subparsers.add_parser("list", aliases=['ls'], help="List all slaves in repository")
    list_parser.add_argument("profile", nargs='?', help="List all slaves of PROFILE")
    list_parser.set_defaults(func=list)

    sync_parser = subparsers.add_parser("sync", help="Synchronizes master and slaves")
    sync_parser.add_argument("profile", help="Synchronize all slaves of PROFILE")
    sync_parser.set_defaults(func=sync)

    version_parser = subparsers.add_parser("--version", aliases=['-v'], help="Prints Jackups version")
    version_parser.set_defaults(func=version)

    args = parser.parse_args()

    # we were run without any arguments, print usage and exit
    if not len(sys.argv) > 1:
        parser.print_help()
        return

    jackup_dir = os.path.join(Path.home(), '.jackup')
    jackup_log = os.path.join(jackup_dir, "log")
    jackup_lock = os.path.join(jackup_dir, "lock")

    # create jackup directory if it does not exist
    if not os.path.isdir(jackup_dir):
        os.mkdir(jackup_dir)

    config = {
        'dir': jackup_dir,
        'log': jackup_log,
        'lock': jackup_lock
    }

    # delegate to relevant functions based on parsed args
    args = vars(args)
    func = args.pop("func")
    func(config, **args)
