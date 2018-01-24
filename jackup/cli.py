import os
import sys
import argparse

from jackup.core import init, add, remove, list, sync

def version(config):
    print('Jackup version 0.1 - alpha')

def main():
    # setup the parser for commandline usage
    parser = argparse.ArgumentParser(description="Jackup: Simple synchronization.")
    subparsers = parser.add_subparsers()

    init_parser = subparsers.add_parser("init", help="Initialize a new repository")
    init_parser.set_defaults(func=init)

    add_parser = subparsers.add_parser("add", help="Add a slave to repository")
    group = add_parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--pull', dest="action", action='store_const', const='pull', help="pull content from slave down to master")
    group.add_argument('--push', dest="action", action='store_const', const='push', help="push masters content to the slave")
    add_parser.add_argument("name", help="name of the slave to add to the repository")
    add_parser.add_argument("path", help="directory used to sync with master")
    add_parser.add_argument("--subdir", default='/', help="subdirectory to pull into")
    add_parser.add_argument('--ssh', nargs='?', dest="port", type=int, const=22, default=0, help="if the slave in on a remote machine")
    add_parser.set_defaults(func=add)

    remove_parser = subparsers.add_parser("remove", aliases=['rm'], help="Remove a slave from repository")
    remove_parser.add_argument("name", help="name of the slave to remove")
    remove_parser.set_defaults(func=remove)

    list_parser = subparsers.add_parser("list", aliases=['ls'], help="List all slaves in repository")
    list_parser.set_defaults(func=list)

    sync_parser = subparsers.add_parser("sync", help="Synchronizes master and slaves")
    sync_parser.set_defaults(func=sync)

    version_parser = subparsers.add_parser("--version", aliases=['-v'], help="Prints Jackups version")
    version_parser.set_defaults(func=version)

    args = parser.parse_args()

    # we were run without any arguments, print usage and exit
    if not len(sys.argv) > 1:
        parser.print_help()
        return

    master_dir = os.path.join(os.getcwd())
    jackup_dir = os.path.join(master_dir, ".jackup")
    jackup_file = os.path.join(jackup_dir, "json")
    jackup_log = os.path.join(jackup_dir, "log")
    jackup_lock = os.path.join(jackup_dir, "lock")

    config = {
        'master': master_dir,
        'dir': jackup_dir,
        'file': jackup_file,
        'log': jackup_log,
        'lock': jackup_lock
    }

    # delegate to relevant functions based on parsed args
    args = vars(args)
    func = args.pop("func")
    func(config, **args)
