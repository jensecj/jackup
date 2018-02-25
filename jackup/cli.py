import os
import sys
import argparse
from pathlib import Path

from jackup.core import add, edit, remove, list, sync

def main():
    # setup the parser for commandline usage
    parser = argparse.ArgumentParser(description="Jackup: Simple synchronization.")
    parser.add_argument('-v', '--version', action='version', version='%(prog)s v0.3')

    subparsers = parser.add_subparsers()

    add_parser = subparsers.add_parser("add", help="Add a task to a profile")
    add_parser.add_argument("profile_name", help="profile to add tasks to")
    add_parser.add_argument("task_name", help="name of the task to add to the profile")
    add_parser.add_argument("source", help="source to sync from, can be a directory or file")
    add_parser.add_argument("destination", help="destination to sync to, can be a directory or file")
    add_parser.add_argument('--order', nargs='?', type=int, default=0, help="order in which the tasks are synchronized")
    add_parser.set_defaults(func=add)

    edit_parser = subparsers.add_parser("edit", help="Edit a task in profile")
    edit_parser.add_argument("profile_name", help="profile containing the task to edit")
    edit_parser.add_argument("task_name", help="name of the task to edit")
    edit_parser.add_argument("--source", help="source to sync from, can be a directory or file")
    edit_parser.add_argument("--destination", help="destination to sync to, can be a directory or file")
    edit_parser.add_argument('--order', type=int, help="order in which the tasks are synchronized")
    edit_parser.set_defaults(func=edit)

    remove_parser = subparsers.add_parser("remove", aliases=['rm'], help="Remove a task from profile")
    remove_parser.add_argument("profile_name", help="profile to remove task from")
    remove_parser.add_argument("task_name", help="name of the task to remove")
    remove_parser.set_defaults(func=remove)

    list_parser = subparsers.add_parser("list", aliases=['ls'], help="List all tasks in profile")
    list_parser.add_argument("profile_name", nargs='?', help="Profile to list tasks of")
    list_parser.set_defaults(func=list)

    sync_parser = subparsers.add_parser("sync", help="Synchronizes a profile")
    sync_parser.add_argument("profile_name", help="Profile with tasks to synchronize")
    sync_parser.set_defaults(func=sync)

    args = parser.parse_args()

    # we were run without any arguments, print usage and exit
    if not len(sys.argv) > 1:
        parser.print_help()
        return

    jackup_dir = os.path.join(Path.home(), '.jackup')
    jackup_log = os.path.join(jackup_dir, "log")

    # create jackup directory if it does not exist
    if not os.path.isdir(jackup_dir):
        os.mkdir(jackup_dir)

    config = {
        'dir': jackup_dir,
        'log': jackup_log,
    }

    # delegate to relevant functions based on parsed args
    args = vars(args)
    func = args.pop("func")
    func(config, **args)
