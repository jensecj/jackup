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

def _jackup_profile_lock(config, profile):
    """
    Returns the path to the profile-lockfile belonging to PROFILE.
    """
    return os.path.join(config['dir'], profile + '.lock')

def add(config, profile, name, source, destination, priority, port):
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

    if name in profile_json:
        printer.warning('This name is already in use')
        print('use `jackup edit <profile> <name>` to change settings inside this slave')
        return

    # if we add a new slave without a priority, place it last in the queue of
    # slaves to synchronize by giving it the largest priority
    if not priority:
        priorities = [ profile_json[slave]['priority'] for slave in profile_json ]

        if len(priorities) == 0:
            priority = 0
        else:
            priority = max(priorities) + 1

    profile_json[name] = { 'source': source, 'destination': destination, 'priority': priority }

    with open(profile_file, 'w') as profile_db:
        json.dump(profile_json, profile_db, indent=4)

    print("added " + profile + '/' + name)

def edit(config, profile, name, source, destination, priority, port):
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

    if priority:
        profile_json[name]['priority'] = priority

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

    table = [ ['name', 'source', 'destination', 'priority'] ]

    sorted_slaves = sorted(profile_json, key=lambda k: profile_json[k]['priority'])

    for slave in sorted_slaves:
        table.append([ slave, profile_json[slave]['source'], profile_json[slave]['destination'], str(profile_json[slave]['priority']) ])

    tp.print_table(table)

def _rsync(config, slave, src, dest, excludes=['.jackup']):
    rsync_args = ['--log-file=' + config['log'],
                  '--partial', '--progress', '--archive',
                  '--recursive', '--human-readable',
                  #'--timeout=30',
                  '--copy-links',
                  '--new-compress',
                  '--checksum',
                  # '--quiet',
                  '--verbose',
                  '--dry-run',
                  '--delete'
    ]

    for ex in excludes:
        rsync_args += ['--exclude=' + ex]

    cmd_rsync = subprocess.run(['rsync'] + rsync_args + [src, dest], stderr=subprocess.PIPE)
    rsync_stderr = str(cmd_rsync.stderr, 'utf-8', 'ignore').strip()
    return rsync_stderr

def _sync_slave(config, slave, record):
    printer.success(slave + ": " + record['source'] + ' -> ' + record['destination'])

    excludes = []
    ignore_file = os.path.join(record['source'], '.jackupignore')
    if os.path.isfile(ignore_file):
        with open(ignore_file, 'r') as ignore_db:
            for line in ignore_db:
                excludes.append(line.strip())

    rsync_stderr = _rsync(config, slave, record['source'], record['destination'], excludes)

    if rsync_stderr:
        printer.error('failed syncing ' + slave)
        printer.error(rsync_stderr)
        return False

    printer.success('completed syncing ' + slave)
    return True

def sync(config, profile):
    """
    Synchronizes all slaves in PROFILE.
    """
    profile_file = _jackup_profile(config, profile)
    if not os.path.isfile(profile_file):
        printer.error("That profile does not exist.")
        return

    # only try syncing if we can lock the repository
    lockfile = _jackup_profile_lock(config, profile)
    if not os.path.isfile(lockfile):
        # create the lock when we acquire it
        open(lockfile, 'w').close()
    else:
        printer.error("`jackup sync` is already running for this profile")
        return

    with open(profile_file, 'r') as profile_db:
        profile_json = json.load(profile_db)

    sorted_slaves = sorted(profile_json, key=lambda k: profile_json[k]['priority'])

    syncs = 0

    for slave in sorted_slaves:
        print('syncing ' + slave)
        if _sync_slave(config, slave, profile_json[slave]):
            syncs += 1

    slave_count = str(syncs) + '/' + str(len(sorted_slaves))

    if syncs == 0 and len(sorted_slaves) > 0:
        slave_count = printer.RED(slave_count)
    elif syncs < len(sorted_slaves):
        slave_count = printer.YELLOW(slave_count)
    else:
        slave_count = printer.GREEN(slave_count)

    print('synchronized ' + slave_count + " slaves")
    print('completed syncing ' + profile)

    # free the lock for the profile
    os.remove(lockfile)
