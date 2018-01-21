import os
import json
import subprocess

import jackup.tableprinter as tp
import jackup.sysutils as su
import jackup.printhelper as printer

def is_jackup_repo(config):
    """
    Returns whether the current working directory is a valid repository.
    """
    return os.path.isfile(config['file'])

def jackup_repo_or_die(config):
    """
    Exits program if we are not in a jackup repository
    """
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

        if not su.ssh_can_connect(host, str(port)):
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

def _path_to_local_slave(slave):
    """
    Returns the local filesystem path to the slave.
    """
    mnt_point = su.mountpoint_from_uuid(slave['uuid'])
    if not mnt_point:
        return

    return su.path_from_uuid_relpath(slave['uuid'], slave['relpath'])

def _path_to_ssh_slave(slave):
    """
    Returns the remote path to the slave.
    """
    if not su.ssh_can_connect(slave['host'], slave['port']):
        return

    return slave['host'] + ":" + slave['path']

def _rsync(config, slave, source, dest):
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
                  # '--dry-run',
                  '--delete'
    ]

    if slave['type'] == 'ssh':
        rsync_args += ['-e', 'ssh -p' + slave['port']]
        rsync_args += ['--port', slave['port']]

    cmd_rsync = subprocess.run(['rsync'] + rsync_args + [source, dest], stderr=subprocess.PIPE)
    rsync_stderr = str(cmd_rsync.stderr, 'utf-8', 'ignore').strip()
    return rsync_stderr

def _sync_slave(config, slave):
    """
    Figures out whether to pull or push a slave, and delegates syncing to `rsync`.
    """
    if slave['type'] == 'local':
        sync_path = _path_to_local_slave(slave)
        if sync_path:
            printer.success(slave['name'] + ' found at ' + sync_path + ", syncing...")
        else:
            printer.warning(slave['name'] + ' is not mounted, skipping')
    elif slave['type'] == 'ssh':
        sync_path = _path_to_ssh_slave(slave)
        if sync_path:
            printer.success(slave['name'] + ' is online, syncing...')
        else:
            printer.warning(slave['name'] + " unable to connect to " + slave['host'] + ", skipping.")
            return

    # skip if slave is unavailable
    if not sync_path:
        return False

    if slave['action'] == 'pull':
        rsync_stderr = _rsync(config, slave, sync_path, config['master'])
    elif slave['action'] == 'push':
        rsync_stderr = _rsync(config, slave, config['master'], sync_path)

    if rsync_stderr:
        printer.error('failed syncing ' + slave['name'])
        print(rsync_stderr)
        return False

    printer.success('completed syncing ' + slave['name'])
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
        if _sync_slave(config, slave):
            pulls += 1

    if any(to_pull) and pulls == 0:
        printer.error('failed to pull any slaves')

    to_push = [ slave for slave in jackup_json['slaves'] if slave['action'] == 'push' ]
    for slave in to_push:
        print('trying to push to ' + slave['name'])
        if _sync_slave(config, slave):
            pushes += 1

    if any(to_push) and pushes == 0:
        printer.error('failed to push any slaves')

    pulls_string = str(pulls) + " / " + str(len(to_pull)) + " pulls"
    pushes_string = str(pushes) + " / " + str(len(to_push)) + " pushes"

    if len(to_pull) > 0 and pulls == 0:
        pulls_string = printer.RED(pulls_string)
    elif len(to_pull) > 0 and pulls < len(to_pull):
        pulls_string = printer.YELLOW(pulls_string)
    else:
        pulls_string = printer.GREEN(pulls_string)

    if len(to_push) > 0 and pushes == 0:
        pushes_string = printer.RED(pushes_string)
    elif len(to_push) > 0 and pushes < len(to_push):
        pushes_string = printer.YELLOW(pushes_string)
    else:
        pushes_string = printer.GREEN(pushes_string)

    print('syncing complete: ' + pulls_string + ', ' + pushes_string)
