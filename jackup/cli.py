import os
import sys
import argparse
import pkg_resources
from pathlib import Path

from jackup.core import list, sync
from jackup.config import Config


def main():
    semver = pkg_resources.require("jackup")[0].version
    parser = argparse.ArgumentParser(description="Jackup: Simple Synchronization.")
    parser.add_argument(
        "-v", "--version", action="version", version="%(prog)s " + semver
    )
    subparsers = parser.add_subparsers()

    list_parser = subparsers.add_parser(
        "list", aliases=["ls"], help="List tasks in profiles"
    )
    list_parser.add_argument("profiles", nargs="*", help="Profiles to list tasks of")
    list_parser.set_defaults(func=list)

    sync_parser = subparsers.add_parser("sync", help="Synchronizes a profile")
    # TODO: allow multiple profiles, and sync in order
    sync_parser.add_argument("profile_name", help="Profile with tasks to synchronize")
    sync_parser.add_argument(
        "-q", "--quiet", nargs="?", type=bool, help="Be less verbose"
    )
    sync_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Be more verbose"
    )
    sync_parser.set_defaults(func=sync)

    args = parser.parse_args()

    # print usage if run without arguments
    if not len(sys.argv) > 1:
        parser.print_help()
        return

    jackup_dir = os.path.expanduser("~/.config/jackup/")
    jackup_log = os.path.join(jackup_dir, "log")  # TODO: log to /var/log?

    # create jackup directory if it does not exist
    if not os.path.isdir(jackup_dir):
        os.mkdir(jackup_dir)

    config = Config(jackup_path=jackup_dir, log_path=jackup_log)

    # delegate to relevant functions based on parsed args
    args = vars(args)
    func = args.pop("func")
    func(config, **args)
