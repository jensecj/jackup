#!/usr/bin/python

import os
import sys
import argparse
import json
import subprocess
import tableprinter as tp
import sysutils as su

def can_connect(host, port):
    """
    Returns whether we can connect to a host through ssh.
    """
    cmd_ssh = subprocess.run(['ssh', '-p', port, host, 'exit 0'])

    # 0 means no errors, c-style.
    return not cmd_ssh.returncode

def is_jackup_repo(config):
    """
    Returns whether the current working directory is a valid repository.
    """
    return os.path.isfile(config['file'])

def jackup_repo_or_die(config):
    if not is_jackup_repo(config):
        print("This is not a jackup repository.")
        print("use 'jackup init' to initialize")
        exit(1)

def init(config):
    """
    Handler for `jackup init`.
    Initializes a new repository in the current working directory.
    """
    if is_jackup_repo(config):
        print("This is already a jackup repository!")
        return

    os.mkdir(config['dir'])

    with open(config['file'], 'w') as jackup_db:
        json.dump({ "master": config['master'], "slaves": [] }, jackup_db)

    print("Initialized a new repository in " + config['master'])

def add(config, push, pull, ssh, port, name, path):
    """
    Handler for `jackup add`.
    Adds a new slave to the repository.

    A slave can either be a local folder, or a folder on some remote machine
    reachable through ssh.
    It can also be either a push, or a pull slave, based on whether we want to
    push the contents of the master directory to the slave, or pull the contents
    of the slave down to the master directory.
    """
    jackup_repo_or_die(config)

    with open(config['file'], 'r') as jackup_db:
        jackup_json = json.load(jackup_db)

    names = [ slave['name'] for slave in jackup_json['slaves'] ]
    if (name in names):
        print("that name already exists in the repository")
        return

    if push:
        action = 'push'
    elif pull:
        action = 'pull'

    if ssh:
        type = "ssh"
        host, path = path.rsplit(':')

        if not can_connect(host, str(port)):
            print("unable to connect to " + host)
            return
    else:
        type = "local"

    new_slave = { "name": name, "action": action, "type": type, "path": path }

    if type == "ssh":
        new_slave['host'] = host
        new_slave['port'] = str(port)
    elif type == 'local':
        uuid, relpath = su.uuid_relpath_pair_from_path(path)
        new_slave['uuid'] = uuid
        new_slave['relpath'] = relpath

    jackup_json['slaves'].append(new_slave)

    with open(config['file'], 'w') as jackup_db:
        json.dump(jackup_json, jackup_db)

    print("added slave " + name)

def remove(config, name):
    """
    Remove a slave from the repository.
    """
    jackup_repo_or_die(config)

    with open(config['file'], 'r') as jackup_db:
        jackup_json = json.load(jackup_db)

    names = [ slave['name'] for slave in jackup_json['slaves'] ]
    if (name not in names):
        print(name + " is not in the repository")
        return

    for slave in jackup_json['slaves']:
        if (slave["name"] == name):
            jackup_json['slaves'].remove(slave)
            break

    with open(config['file'], 'w') as jackup_db:
        json.dump(jackup_json, jackup_db)

    print("removed slave " + name)

def list(config):
    """
    List all slaves in the repository.
    """
    jackup_repo_or_die(config)

    with open(config['file'], 'r') as jackup_db:
        jackup_json = json.load(jackup_db)
        master_path = jackup_json['master']

    if not jackup_json['slaves']:
        print("this repository has no slaves.")
        print("use 'jackup add <path>' to add some")
        return

    print("MASTER: " + config['master'] + " will duplicate to:")
    table = [['name', 'action', 'type', 'path', 'uuid/relpath / host/port']]

    slaves = [ slave for slave in jackup_json['slaves'] if slave['action'] == 'pull' ]
    slaves += [ slave for slave in jackup_json['slaves'] if slave['action'] == 'push' ]

    for slave in slaves:
        if slave['type'] == 'local':
            table.append([slave['name'], slave['action'], slave['type'], slave["path"], slave['uuid']+'/'+slave['relpath']])
        elif slave['type'] == 'ssh':
            table.append([slave['name'], slave['action'], slave['type'], slave["path"], slave['host']+'/'+slave['port']])

    tp.print_table(table)

def sync_path_local(slave):
    """
    Returns the local filesystem path to the slave.
    """
    mnt_point = su.mountpoint_from_uuid(slave['uuid'])
    if not mnt_point:
        print(slave['name'] + " is not mounted, skipping.")
        return

    print(slave['name'] + " found at " + mnt_point)
    return su.path_from_uuid_relpath(slave['uuid'], slave['relpath'])

def sync_path_ssh(slave):
    """
    Returns the remote path to the slave.
    """
    if not can_connect(slave['host'], slave['port']):
        print(slave['name'] + " unable to connect to " + slave['host'] + ", skipping.")
        return

    print(slave['host'] + " is online")
    return slave['host'] + ":" + slave['path']

def rsync(config, slave, source, dest):
    """
    Calls rsync to sync the master directory and the slave.
    """
    rsync_args = ['--exclude=.jackup',
                  '--log-file=' + config['log'],
                  '--partial', '--progress', '--archive',
                  '--recursive', '--human-readable',
                  '--timeout=30',
                  '--copy-links',
                  '--new-compress',
                  '--checksum',
                  # '--quiet',
                  '--verbose',
                  '--dry-run',
                  # '--delete'
    ]

    if slave['type'] == 'ssh':
        rsync_args += ['-e', 'ssh -p' + slave['port']]
        rsync_args += ['--port', slave['port']]

    cmd_rsync = subprocess.run(['rsync'] + rsync_args + [source, dest], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    rsync_stdout = str(cmd_rsync.stdout, 'utf-8', 'ignore').strip()
    rsync_stderr = str(cmd_rsync.stderr, 'utf-8', 'ignore').strip()
    return (rsync_stdout, rsync_stderr)

def sync_slave(config, slave):
    """
    Figures out whether to pull or push a slave, and delegates syncing to `rsync`.
    """
    if slave['type'] == 'local':
        sync_path = sync_path_local(slave)
    elif slave['type'] == 'ssh':
        sync_path = sync_path_ssh(slave)

    # skip if slave is unavailable
    if not sync_path:
        return False

    if slave['action'] == 'pull':
        rsync_output, rsync_stderr = rsync(config, slave, sync_path, config['master'])
    elif slave['action'] == 'push':
        rsync_output, rsync_stderr = rsync(config, slave, config['master'], sync_path)

    if rsync_output:
        print(rsync_output)

    if rsync_stderr:
        print('failed syncing ' + slave['name'])
        print(rsync_stderr)
        return False

    print('done syncing ' + slave['name'])
    return True

def sync(config):
    """
    Handler for `jackup sync`.
    Starts syncing the master directory with its slaves.
    Starts with pulling all available pull-slaves into the master, then pushing the
    master to all push-slaves.
    """
    jackup_repo_or_die(config)

    print("Syncing master: " + config['master'])

    with open(config['file'], 'r') as jackup_db:
        jackup_json = json.load(jackup_db)

    pulls = 0
    pushes = 0

    to_pull = [ slave for slave in jackup_json['slaves'] if slave['action'] == 'pull' ]
    for slave in to_pull:
        print('trying to pull from ' + slave['name'])
        if sync_slave(config, slave):
            pulls += 1

    if any(to_pull) and pulls == 0:
        print('failed to pull any slaves')

    to_push = [ slave for slave in jackup_json['slaves'] if slave['action'] == 'push' ]
    for slave in to_push:
        print('trying to push to ' + slave['name'])
        if sync_slave(config, slave):
            pushes += 1

    if any(to_push) and pushes == 0:
        print('failed to push any slaves')

def main():
    # setup the parser for commandline usage
    parser = argparse.ArgumentParser(description="Jackup: Simple synchronization.")
    subparsers = parser.add_subparsers()

    init_parser = subparsers.add_parser("init", help="Initialize a new repository")
    init_parser.set_defaults(func=init)

    add_parser = subparsers.add_parser("add", help="Add a slave to repository")
    group = add_parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--push', action='store_true', help="push masters content to the slave")
    group.add_argument('--pull', action='store_true', help="pull content from slave down to master")
    add_parser.add_argument('--ssh', action='store_true', help="if the slave in on a remote machine")
    add_parser.add_argument('--port', type=int, default=22, help="port used to connect to remote machine")
    add_parser.add_argument("name", help="name of the slave to add to the repository")
    add_parser.add_argument("path", help="directory used to sync with master")
    add_parser.set_defaults(func=add)

    remove_parser = subparsers.add_parser("remove", aliases=['rm'], help="Remove a slave from repository")
    remove_parser.add_argument("name", help="name of the slave to remove")
    remove_parser.set_defaults(func=remove)

    list_parser = subparsers.add_parser("list", aliases=['ls'], help="List all slaves in repository")
    list_parser.set_defaults(func=list)

    sync_parser = subparsers.add_parser("sync", help="Synchronizes master and slaves")
    sync_parser.set_defaults(func=sync)

    args = parser.parse_args()

    # we were run without any arguments, print usage and exit
    if not len(sys.argv) > 1:
        parser.print_help()
        return

    master_dir = os.path.join(os.getcwd())
    jackup_dir = os.path.join(master_dir, ".jackup")
    jackup_file = os.path.join(jackup_dir, "jackup.json")
    jackup_log = os.path.join(jackup_dir, "jackup.log")

    config = { 'master': master_dir, 'dir': jackup_dir, 'file': jackup_file, 'log': jackup_log }

    # delegate to relevant functions based on parsed args
    args = vars(args)
    func = args.pop("func")
    func(config, **args)

if __name__ == "__main__":
    main()
