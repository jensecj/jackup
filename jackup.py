#!/usr/bin/python

import os
import sys
import argparse
import json
import subprocess
import tableprinter as tp

def mountpoint_from_uuid(uuid):
    """
    Returns the path where a device with UUID is mounted.
    If the device is not mounted, then return the empty string.
    """
    cmd_findmnt = subprocess.run(["findmnt", "-rn", "-S", "UUID=" + uuid, "-o", "TARGET"], stdout=subprocess.PIPE)
    return str(cmd_findmnt.stdout, 'utf-8', 'ignore').strip()

# uuids = ["28B88482B884506C", "027E2FC17E2FAC7B"]
# for uuid in uuids:
#     mnt_point = mountpoint_from_uuid(uuid)
#     if mnt_point:
#         print(uuid + " is mounted at " + mnt_point)
#     else:
#         print(uuid + " is not mounted")




def uuid_relpath_pair_from_path(path):
    """
    Generates a (UUID, relative path) pair from a path on the file system.
    This is done by figuring out which device the path belongs to, and then
    finding its mountpoint, the relative path is then calculated based on where
    the device is mounted.
    """
    cmd_df = subprocess.run(['df', '--output=source', path], stdout=subprocess.PIPE)
    device = str(cmd_df.stdout, 'utf-8', 'ignore')[10:].strip()

    cmd_lsblk = subprocess.run(['lsblk', '-f', device, '-oUUID'], stdout=subprocess.PIPE)
    uuid = str(cmd_lsblk.stdout, 'utf-8', 'ignore')[4:].strip()

    cmd_mountpoint = subprocess.run(['lsblk', '-f', device, '-oMOUNTPOINT'], stdout=subprocess.PIPE)
    mountpoint = str(cmd_mountpoint.stdout, 'utf-8', 'ignore')[10:].strip()

    uuid_relative_path = path
    if path.startswith(mountpoint):
        uuid_relative_path = path[len(mountpoint):].strip('/')

    return (uuid, uuid_relative_path)

# paths = ["/mnt/extern/images", "/home/jens/test"]
# for p in paths:
#     print(uuid_relpath_pair_from_path(p))




def path_from_uuid_relpath(uuid, relpath):
    """
    Reifies a filesystem path from a (UUID, relative path) pair.
    This is done by finding the mountpoint of the device belonging to the UUID, then
    glueing the relative path onto mountpoint.
    """
    mnt_point = mountpoint_from_uuid(uuid)
    return os.path.join(mnt_point, relpath)

# uuid_paths = [["027E2FC17E2FAC7B", "images"],
#               ["d047f2a2-6a9b-4f9c-9c3b-bd3c418babe9", "home/jens/vault"]]
# for uu,pp in uuid_paths:
#     print(uu + " + " + pp + " = " + path_from_uuid_relpath(uu,pp))




def is_jackup_repo(config):
    """
    Returns whether the current working directory is a valid repository.
    """
    _, _, jackup_file, _ = config
    return os.path.isfile(jackup_file)

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
    repo_dir, jackup_dir, jackup_file, jackup_log = config

    if is_jackup_repo(config):
        print("This is already a jackup repository!")
    else:
        print("Initializing a new repository in " + os.getcwd())
        os.mkdir(jackup_dir)

        with open(jackup_file, 'w') as jackup_db:
            json.dump({ "master": os.getcwd(), "slaves": [] }, jackup_db)

def can_connect(host, port):
    """
    Returns whether we can connect to a host through ssh.
    """
    cmd_ssh = subprocess.run(['ssh', '-p', port, host, 'exit 0'])

    # 0 means no errors, c-style.
    return not cmd_ssh.returncode

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
    repo_dir, jackup_dir, jackup_file, jackup_log = config

    jackup_repo_or_die(config)

    with open(jackup_file, 'r') as jackup_db:
        jackup_json = json.load(jackup_db)

    names = [ p['name'] for p in jackup_json['slaves'] ]
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

    new_rec = {"name": name, "action": action, "type": type, "path": path}

    if type == "ssh":
        new_rec['host'] = host
        new_rec['port'] = str(port)
    elif type == 'local':
        uuid, relpath = uuid_relpath_pair_from_path(path)
        new_rec['uuid'] = uuid
        new_rec['relpath'] = relpath

    jackup_json['slaves'].append(new_rec)

    with open(jackup_file, 'w') as jackup_db:
        json.dump(jackup_json, jackup_db)

    print("added slave " + '<'+name+'>')

def remove(config, name):
    """
    Remove a slave from the repository.
    """
    repo_dir, jackup_dir, jackup_file, jackup_log = config

    jackup_repo_or_die(config)

    with open(jackup_file, 'r') as jackup_db:
        jackup_json = json.load(jackup_db)

    names = map((lambda s: s["name"]), jackup_json['slaves'])
    if (name not in names):
        print('<'+name+'>' + " is not in the repository")
        return

    for s in jackup_json['slaves']:
        if (s["name"] == name):
            jackup_json['slaves'].remove(s)
            break

    with open(jackup_file, 'w') as jackup_db:
        json.dump(jackup_json, jackup_db)

    print("removed slave " + '<'+name+'>')

def list(config):
    """
    List all slaves in the repository.
    """
    repo_dir, jackup_dir, jackup_file, jackup_log = config

    jackup_repo_or_die(config)

    with open(jackup_file, 'r') as jackup_db:
        jackup_json = json.load(jackup_db)
        master_path = jackup_json['master']

    if not jackup_json['slaves']:
        print("this repository has no slaves.")
        print("use 'jackup add <path>' to add some")
    else:
        print("MASTER: " + master_path + " will duplicate to:")
        table = [['name', 'action', 'type', 'path', 'uuid/relpath / host/port']]

        slaves = [ p for p in jackup_json['slaves'] if p['action'] == 'pull' ]
        slaves += [ p for p in jackup_json['slaves'] if p['action'] == 'push' ]

        for s in slaves:
            if s['type'] == 'local':
                table.append([s['name'], s['action'], s['type'], s["path"], s['uuid']+'/'+s['relpath']])
            elif s['type'] == 'ssh':
                table.append([s['name'], s['action'], s['type'], s["path"], s['host']+'/'+s['port']])

        tp.print_table(table)

def sync_path_local(slave):
    """
    Returns the local filesystem path to the slave.
    """
    repo_dir, jackup_dir, jackup_file, jackup_log = config

    mnt_point = mountpoint_from_uuid(slave['uuid'])
    if not mnt_point:
        print(slave['name'] + " is not mounted, skipping.")
        return

    print(slave['name'] + " found at " + mnt_point)
    return path_from_uuid_relpath(slave['uuid'], slave['relpath'])

def sync_path_ssh(slave):
    """
    Returns the remote path to the slave.
    """
    if not can_connect(slave['host'], slave['port']):
        print(slave['name'] + " unable to connect to " + slave['host'] + ", skipping.")
        return

    print(slave['host'] + " is online")
    return slave['host'] + ":" + slave['path']

def rsync(slave, source, dest):
    """
    Calls rsync to sync the master directory and the slave.
    """
    repo_dir, jackup_dir, jackup_file, jackup_log = config

    rsync_args = ['--exclude=.jackup',
                  '--log-file=' + jackup_log,
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

def sync_slave(slave):
    """
    Figures out whether to pull or push a slave, and delegates syncing to `rsync`.
    """
    repo_dir, jackup_dir, jackup_file, jackup_log = config

    if slave['type'] == 'local':
        sync_path = sync_path_local(slave)
    elif slave['type'] == 'ssh':
        sync_path = sync_path_ssh(slave)

    # skip if slave is unavailable
    if not sync_path:
        return False

    if slave['action'] == 'pull':
        rsync_output, rsync_stderr = rsync(slave, sync_path, repo_dir)
    elif slave['action'] == 'push':
        rsync_output, rsync_stderr = rsync(slave, repo_dir, sync_path)

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
    repo_dir, jackup_dir, jackup_file, jackup_log = config

    jackup_repo_or_die(config)

    print("Syncing master: " + repo_dir)

    with open(jackup_file, 'r') as jackup_db:
        jackup_json = json.load(jackup_db)

    pulls = 0
    pushes = 0

    to_pull = [ p for p in jackup_json['slaves'] if p['action'] == 'pull' ]
    for pu in to_pull:
        print('trying to pull from ' + pu['name'])
        if sync_slave(pu):
            pulls += 1

    if any(to_pull) and pulls == 0:
        print('failed to pull any slaves')

    to_push = [ p for p in jackup_json['slaves'] if p['action'] == 'push' ]
    for pu in to_push:
        print('trying to push to ' + pu['name'])
        if sync_slave(pu):
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

    repo_dir = os.path.join(os.getcwd())
    jackup_dir = os.path.join(repo_dir, ".jackup")
    jackup_file = os.path.join(jackup_dir, "jackup.json")
    jackup_log = os.path.join(jackup_dir, "jackup.log")

    config = [repo_dir, jackup_dir, jackup_file, jackup_log]

    # delegate to relevant functions based on parsed args
    args = vars(args)
    func = args.pop("func")
    func(config, **args)

if __name__ == "__main__":
    main()
