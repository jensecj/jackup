#!/usr/bin/python

import os
import sys
import argparse
import json
import subprocess
import tableprinter as tp

def mountpoint_from_uuid(uuid):
    """Returns the path where a device with UUID is mounted, if it is not
    mounted, then return empty."""
    cmd_findmnt = subprocess.run(["findmnt", "-rn", "-S", "UUID=" + uuid, "-o", "TARGET"], stdout=subprocess.PIPE)
    # convert from byte-string, and remove the new-lines
    return str(cmd_findmnt.stdout, 'utf-8', 'ignore').strip()

uuids = ["28B88482B884506C", "027E2FC17E2FAC7B"]

# for uuid in uuids:
#     mnt_point = mountpoint_from_uuid(uuid)
#     if mnt_point:
#         print(uuid + " is mounted at " + mnt_point)
#     else:
#         print(uuid + " is not mounted")

def uuid_relpath_pair_from_path(path):
    # print("= path: " + path)

    cmd_df = subprocess.run(['df', '--output=source', path], stdout=subprocess.PIPE)
    device = str(cmd_df.stdout, 'utf-8', 'ignore')[10:].strip()
    # print("= device: " + device)

    cmd_lsblk = subprocess.run(['lsblk', '-f', device, '-oUUID'], stdout=subprocess.PIPE)
    uuid = str(cmd_lsblk.stdout, 'utf-8', 'ignore')[4:].strip()
    # print("= uuid: " + uuid)

    cmd_mountpoint = subprocess.run(['lsblk', '-f', device, '-oMOUNTPOINT'], stdout=subprocess.PIPE)
    mountpoint = str(cmd_mountpoint.stdout, 'utf-8', 'ignore')[10:].strip()
    # print("= mountpoint: " + mountpoint)

    uuid_relative_path = path
    if path.startswith(mountpoint):
        uuid_relative_path = path[len(mountpoint):].strip('/')

    return (uuid, uuid_relative_path)

paths = ["/mnt/extern/images", "/home/jens/test"]

# for p in paths:
#     print(uuid_relpath_pair_from_path(p))

def path_from_uuid_relpath(uuid, relpath):
    mnt_point = mountpoint_from_uuid(uuid)
    return os.path.join(mnt_point, relpath)

uuid_paths = [["027E2FC17E2FAC7B", "images"],
              ["d047f2a2-6a9b-4f9c-9c3b-bd3c418babe9", "home/jens/vault"]]

# for uu,pp in uuid_paths:
#     print(uu + " + " + pp + " = " + path_from_uuid_relpath(uu,pp))

def get_config():
    repo_dir = os.path.join(os.getcwd())
    jackup_dir = os.path.join(repo_dir, ".jackup")
    jackup_file = os.path.join(jackup_dir, "jackup.json")
    jackup_log = os.path.join(jackup_dir, "jackup.log")

    return (repo_dir, jackup_dir, jackup_file, jackup_log)

def is_jackup_repo():
    _, _, jackup_file, _ = get_config()
    return os.path.isfile(jackup_file)

def init():
    repo_dir, jackup_dir, jackup_file, jackup_log = get_config()

    if is_jackup_repo():
        print("This is already a jackup repository!")
    else:
        print("Initializing a new repository in " + os.getcwd())
        os.mkdir(jackup_dir)

        with open(jackup_file, 'w') as jackup_db:
            json.dump({ "master": os.getcwd(), "slaves": [] }, jackup_db)

def can_connect(host, port):
    cmd_ssh = subprocess.run(['ssh', '-p', port, '-i/home/jens/.ssh/stuetop', host, 'exit 0'])

    # 0 means no errors, c-style.
    return not cmd_ssh.returncode

def remote_exists(host, path, port):
    cmd_ssh = subprocess.run(['ssh', '-p', port, '-i/home/jens/.ssh/stuetop', host, 'test -d', path])

    # 0 means no errors, c-style.
    if cmd_ssh.returncode == 0:
        return True
    elif cmd_ssh.returncode == 1:
        return False

def add(ssh, port, name, path):
    repo_dir, jackup_dir, jackup_file, jackup_log = get_config()

    port = str(port)

    if not is_jackup_repo():
        print("This is not a jackup repository.")
        print("use 'jackup init' to initialize")
        return

    with open(jackup_file, 'r') as jackup_db:
        jackup_json = json.load(jackup_db)

    names = map((lambda s: s["name"]), jackup_json['slaves'])
    if (name in names):
        print("that name already exists in the repository")
        return

    if ssh:
        type = "ssh"
        host, path = path.rsplit(':')

        if not can_connect(host, port):
            print("unable to connect to " + host)
            return
    else:
        type = "local"

    new_rec = {"name": name, "type": type, "path": path}

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

def remove(name):
    repo_dir, jackup_dir, jackup_file, jackup_log = get_config()

    if not is_jackup_repo():
        print("This is not a jackup repository.")
        print("use 'jackup init' to initialize")
        return

    with open(jackup_file, 'r') as jackup_db:
        jackup_json = json.load(jackup_db)

    names = map((lambda s: s["name"]), jackup_json['slaves'])
    if (name not in names):
        print('<'+name+'>' + " is not in the repository")
        return

    removed = False
    for s in jackup_json['slaves']:
        if (s["name"] == name):
            jackup_json['slaves'].remove(s)
            removed = True
            break

    # jackup_json['slaves'].remove(str(path))

    with open(jackup_file, 'w') as jackup_db:
        json.dump(jackup_json, jackup_db)

    print("removed slave " + '<'+name+'>')

def list():
    repo_dir, jackup_dir, jackup_file, jackup_log = get_config()

    if not is_jackup_repo():
        print("This is not a jackup repository.")
        print("use 'jackup init' to initialize")
        return

    with open(jackup_file, 'r') as jackup_db:
        jackup_json = json.load(jackup_db)
        master_path = jackup_json['master']

    if not jackup_json['slaves']:
        print("this repository has no slaves.")
        print("use 'jackup add <path>' to add some")
    else:
        print("MASTER: " + master_path + " will duplicate to:")
        table = [['name', 'type', 'path', 'uuid/relpath / host/port']]
        for s in jackup_json['slaves']:
            if s['type'] == 'local':
                table.append([s['name'], s['type'], s["path"], s['uuid']+'/'+s['relpath']])
            elif s['type'] == 'ssh':
                table.append([s['name'], s['type'], s["path"], s['host']+'/'+s['port']])

        tp.print_table(table)

def slave_print(slave, string):
    print('<' + slave['name'] + '>: ' + string)

def sync_path_local(slave):
    repo_dir, jackup_dir, jackup_file, jackup_log = get_config()

    mnt_point = mountpoint_from_uuid(slave['uuid'])
    if not mnt_point:
        slave_print(slave, "is not mounted, skipping.")
        return

    slave_print(slave, "found at " + mnt_point)
    return path_from_uuid_relpath(slave['uuid'], slave['relpath'])

def sync_path_ssh(slave):
    repo_dir, jackup_dir, jackup_file, jackup_log = get_config()

    if not can_connect(slave['host'], slave['port']):
        slave_print(slave, "unable to connect to " + slave['host'] + ", skipping.")
        return

    slave_print(slave, slave['host'] + " is online")
    return slave['host'] + ":" + slave['path']

def sync():
    repo_dir, jackup_dir, jackup_file, jackup_log = get_config()

    if not is_jackup_repo():
        print("This is not a jackup repository.")
        print("use 'jackup init' to initialize")
        return

    print("Syncing master: " + repo_dir)

    with open(jackup_file, 'r') as jackup_db:
        jackup_json = json.load(jackup_db)

    syncs = 0

    for s in jackup_json['slaves']:
        if s['type'] == 'local':
            sync_path = sync_path_local(s)
        elif s['type'] == 'ssh':
            sync_path = sync_path_ssh(s)

        # skip if slave is unavailable
        if not sync_path:
            continue

        print('<'+s['name']+'>: ' + "syncing to " + sync_path)

        ssh_command = ''
        if s['type'] == 'ssh':
            ssh_command = 'ssh -i/home/jens/.ssh/stuetop'

        cmd_rsync = subprocess.run(['rsync', '--exclude=.jackup',
                                    '-e', ssh_command,
                                    '--partial', '--progress', '--archive',
                                    '--recursive', '--human-readable', '--delete',
                                    '--compress', '--checksum', '--log-file=' + jackup_log,
                                    '--quiet',
                                    '--dry-run',
                                    # '--verbose',
                                    repo_dir, sync_path], stdout=subprocess.PIPE)

        cmd_rsync_output = str(cmd_rsync.stdout, 'utf-8', 'ignore').strip()

        if cmd_rsync_output:
            print(cmd_rsync_output)
        else:
            slave_print(s, 'done syncing')
            syncs += 1

    if syncs == 0:
        print('failed to sync to any targets')

def main():
    parser = argparse.ArgumentParser(description="Jackup: Simple duplication.")
    subparsers = parser.add_subparsers()

    init_parser = subparsers.add_parser("init", help="Initialize a new repository")
    init_parser.set_defaults(func=init)

    add_parser = subparsers.add_parser("add", help="Add a slave to the repository")
    add_parser.add_argument('--ssh', action='store_true', help="if the slave in on a remote machine")
    add_parser.add_argument('--port', type=int, default=22, help="port used to connect to remote machine")
    add_parser.add_argument("name", help="name of the slave to add to the repository")
    add_parser.add_argument("path", help="directory used to sync with master")
    add_parser.set_defaults(func=add)

    remove_parser = subparsers.add_parser("remove", aliases=['rm'], help="Remove a slave from the repository")
    remove_parser.add_argument("name", help="name of the slave to remove")
    remove_parser.set_defaults(func=remove)

    list_parser = subparsers.add_parser("list", aliases=['ls'], help="List all slaves in repository")
    list_parser.set_defaults(func=list)

    sync_parser = subparsers.add_parser("sync", help="Synchronizes the master to the slaves")
    sync_parser.set_defaults(func=sync)

    args = parser.parse_args()
    args = vars(args)
    func = args.pop("func")
    func(**args)

if __name__ == "__main__":
    main()
