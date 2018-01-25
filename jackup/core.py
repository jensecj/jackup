import os
import json
import subprocess

import jackup.tableprinter as tp
import jackup.sysutils as su
import jackup.printhelper as printer

def _jackup_profile(config, profile):
    """
    Returns the path to the profile-file belonging to PROFILE.
    """
    return os.path.join(config['dir'], profile + '.json')

def add(config, profile, name, source, destination, port):
    """
    Add a new slave with NAME, to PROFILE.
    SOURCE/DESTINATION can be either local files/folders, or remote locations,
    accessible through ssh.
    """
    profile_file = _jackup_profile(config, profile)
    if not os.path.isfile(profile_file):
        print('profile does not exist, creating')
        with open(profile_file, 'w') as profile_db:
            json.dump({}, profile_db, indent=4)

    with open(profile_file, 'r') as profile_db:
        profile_json = json.load(profile_db)

    if 'name' in profile_json:
        printer.warning('This name is already in use')
        print('use `jackup edit <profile> <name>` to change settings inside this slave')
        return

    profile_json[name] = { 'source': source, 'destination': destination }

    with open(profile_file, 'w') as profile_db:
        json.dump(profile_json, profile_db, indent=4)

    print("added " + profile + '/' + name)

def edit(config, profile, name, source, destination, port):
    """
    Edit a slave with NAME, in PROFILE.
    Allows changing values of a slave after creation.
    """
    profile_file = _jackup_profile(config, profile)
    if not os.path.isfile(profile_file):
        printer.warning('that profile does not exist')
        return

    with open(profile_file, 'r') as profile_db:
        profile_json = json.load(profile_db)

    if not name in profile_json:
        printer.warning(profile + ' does not have a slave named ' + name)
        return

    if source:
        profile_json[name]['source'] = source

    if destination:
        profile_json[name]['destination'] = destination

    with open(profile_file, 'w') as profile_db:
        json.dump(profile_json, profile_db, indent=4)

    print("edited " + profile + '/' + name)

def remove(config, profile, name):
    """
    Remove an existing slave with NAME, from PROFILE.
    """
    profile_file = _jackup_profile(config, profile)
    if not os.path.isfile(profile_file):
        printer.warning('that profile does not exist')
        return

    with open(profile_file, 'r') as profile_db:
        profile_json = json.load(profile_db)

    if not name in profile_json:
        printer.warning(profile + ' does not have a slave named ' + name)
        return

    profile_json.pop(name)

    with open(profile_file, 'w') as profile_db:
        json.dump(profile_json, profile_db, indent=4)

    print("removed " + profile + '/' + name)

def list(config, profile):
    """
    List all available profiles, or, if given PROFILE, list all slaves in that
    profile.
    """
    if not profile:
        print('Profiles:')
        for file in os.listdir(config['dir']):
            if file.endswith('.json'):
                print('* ' + file[:-5])
        return

    profile_file = _jackup_profile(config, profile)
    if not os.path.isfile(profile_file):
        printer.warning('that profile does not exist')
        return

    with open(profile_file, 'r') as profile_db:
        profile_json = json.load(profile_db)

    table = [['name', 'source', 'destination']]

    for slave in profile_json:
        table.append([ slave, profile_json[slave]['source'], profile_json[slave]['destination'] ])

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
    """
    Synchronizes all slaves in PROFILE.
    """
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
