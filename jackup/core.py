import os
import json
import subprocess

import jackup.tableprinter as tp
import jackup.sysutils as su
import jackup.printhelper as printer

def _jackup_profile(config, profile):
    return  os.path.join(config['dir'], profile + '.json')

def add(config, profile, name, source, destination, port):
    print(config)
    print(profile)
    print(name)
    print(source)
    print(destination)
    print(port)

    profile_file = _jackup_profile(config, profile)
    if not os.path.isfile(profile_file):
        print('profile does not exist, creating')
        with open(profile_file, 'w') as profile_db:
            json.dump([], profile_db, indent=4)

    with open(profile_file, 'r') as profile_db:
        profile_json = json.load(profile_db)

    if name in [ n['name'] for n in profile_json if n['name'] == name ]:
        printer.warning('This name is already in use.')
        print('use `jackup edit <profile> <name>` to change settings inside this slave.')
        return

    record = { 'name': name, 'source': source, 'destination': destination }

    profile_json.append(record)

    with open(profile_file, 'w') as profile_db:
        json.dump(profile_json, profile_db, indent=4)

    print("added slave " + name)

def add2(config, action, name, path, subdir, port):
    """
    Handler for `jackup add`.
    Adds a new slave to the repository.

    A slave can either be a local folder, or a folder on some remote machine
    reachable through ssh.
    It can also be either a push, or a pull slave, based on whether we want to
    push the contents of the master directory to the slave, or pull the contents
    of the slave down to the master directory.
    """
    with open(config['file'], 'r') as jackup_db:
        jackup_json = json.load(jackup_db)

    names = [ slave['name'] for slave in jackup_json['slaves'] ]
    if (name in names):
        print("that name already exists in the repository")
        return

    if port:
        type = "ssh"
        host, relpath = path.rsplit(':')
    else:
        type = "local"

    new_slave = { "name": name, "action": action, "type": type }

    if type == "ssh":
        new_slave['host'] = host
        new_slave['port'] = str(port)
        new_slave['relpath'] = relpath
        new_slave['subdir'] = subdir
    elif type == 'local':
        uuid, relpath = su.uuid_relpath_pair_from_path(path)
        new_slave['uuid'] = uuid
        new_slave['relpath'] = relpath

    jackup_json['slaves'].append(new_slave)

    with open(config['file'], 'w') as jackup_db:
        json.dump(jackup_json, jackup_db, indent=4)

    print("added slave " + name)

def remove(config, profile, name):
    pass

def remove2(config, name):
    """
    Remove a slave from the repository.
    """
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
        json.dump(jackup_json, jackup_db, indent=4)

    print("removed slave " + name)

def list(config, profile):
    if not profile:
        print('Profiles:')
        for file in os.listdir(config['dir']):
            if file.endswith('.json'):
                print('* ' + file[:-5])
        return

    profile_file = _jackup_profile(config, profile)

    with open(profile_file, 'r') as profile_db:
        profile_json = json.load(profile_db)

    table = [['name', 'source', 'destination']]

    for slave in profile_json:
        table.append([slave['name'], slave['source'], slave['destination']])

    tp.print_table(table)

def list2(config, profile):
    """
    List all slaves in the repository.
    """
    with open(config['file'], 'r') as jackup_db:
        jackup_json = json.load(jackup_db)
        master_path = jackup_json['master']

    if not jackup_json['slaves']:
        print("this repository has no slaves.")
        print("use 'jackup add <path>' to add some")
        return

    table = [['name', 'action', 'type', 'UUID / host', 'relative path']]

    # sort slaves first by pull, the by push
    slaves = [ slave for slave in jackup_json['slaves'] if slave['action'] == 'pull' ]
    slaves += [ slave for slave in jackup_json['slaves'] if slave['action'] == 'push' ]

    for slave in slaves:
        if slave['type'] == 'local':
            table.append([slave['name'], slave['action'], slave['type'], slave['uuid'], slave["relpath"]])
        elif slave['type'] == 'ssh':
            table.append([slave['name'], slave['action'], slave['type'], slave['host'], slave["relpath"]])

    tp.print_table(table)

def _rsync(config, slave, src, dest):
    """
    Calls rsync to sync the master directory and the slave.
    """
    rsync_args = ['--exclude=.jackup',
                  '--log-file=' + config['log'],
                  '--partial', '--progress', '--archive',
                  '--recursive', '--human-readable',
                  #'--timeout=30',
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

    cmd_rsync = subprocess.run(['rsync'] + rsync_args + [src, dest], stderr=subprocess.PIPE)
    rsync_stderr = str(cmd_rsync.stderr, 'utf-8', 'ignore').strip()
    return rsync_stderr

def _sync_slave(config, slave):
    """
    Figures out whether to pull or push a slave, and delegates syncing to `rsync`.
    Returns True if synching succeeded, False otherwise.
    """
    src = slave['source']
    dest = slave['destination']

    if not src or not dest:
        printer.warning("unable to locate " + slave['name'] + ", skipping.")
        return False

    printer.success("found " + slave['name'] + ', syncing...')

    printer.success(slave['name'] + ": " + src + ' -> ' + dest)

    rsync_stderr = _rsync(config, slave, src, dest)

    if rsync_stderr:
        printer.error('failed syncing ' + slave['name'])
        printer.error(rsync_stderr)
        return False

    printer.success('completed syncing ' + slave['name'])
    return True

def sync(config, profile):
    profile_path = os.path.join(config['master'], profile + '.json')

    if not os.path.isfile(profile_path):
        printer.error("That profile does not exist.")
        return

    print('syncing ' + profile)

def sync2(config, profile):
    """
    Handler for `jackup sync`.
    Starts syncing the master directory with its slaves.
    Starts with pulling all available pull-slaves into the master, then pushing the
    master to all push-slaves.
    """


    # only try syncing if we can lock the repository
    if not os.path.isfile(config['lock']):
        # create the lock when we acquire it
        open(config['lock'], 'w').close()
    else:
        printer.error("Jackup sync is already running in this repository.")
        return

    print("Syncing master: " + config['master'])

    with open(config['file'], 'r') as jackup_db:
        jackup_json = json.load(jackup_db)

    pulls = 0
    pushes = 0

    # first we try to pull from all pull-slaves into the master directory
    to_pull = [ slave for slave in jackup_json['slaves'] if slave['action'] == 'pull' ]
    for slave in to_pull:
        print('trying to pull from ' + slave['name'])
        if _sync_slave(config, slave):
            pulls += 1

    if any(to_pull) and pulls == 0:
        printer.error('failed to pull any slaves')

    # then we try to push from the master directory to all push-slaves
    to_push = [ slave for slave in jackup_json['slaves'] if slave['action'] == 'push' ]
    for slave in to_push:
        print('trying to push to ' + slave['name'])
        if _sync_slave(config, slave):
            pushes += 1

    if any(to_push) and pushes == 0:
        printer.error('failed to push any slaves')

    # free the sync lock
    os.remove(config['lock'])

    # print results
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
