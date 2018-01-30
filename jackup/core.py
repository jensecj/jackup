import os
import json
import subprocess

import jackup.tableprinter as tp
import jackup.sysutils as su
import jackup.logging as log

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

def add(config, profile, name, source, destination, priority):
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
        log.warning('This name is already in use')
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

    # the record kept for each slave in the profile
    profile_json[name] = { 'source': source, 'destination': destination, 'priority': priority }

    with open(profile_file, 'w') as profile_db:
        json.dump(profile_json, profile_db, indent=4)

    print("added " + profile + '/' + name)

def edit(config, profile, name, source, destination, priority):
    """
    Edit a slave with NAME, in PROFILE.
    Allows changing values of a slave after creation.
    """
    profile_file = _jackup_profile(config, profile)
    if not os.path.isfile(profile_file):
        log.warning('that profile does not exist')
        return

    with open(profile_file, 'r') as profile_db:
        profile_json = json.load(profile_db)

    if not name in profile_json:
        log.warning(profile + ' does not have a slave named ' + name)
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
        log.warning('that profile does not exist')
        return

    with open(profile_file, 'r') as profile_db:
        profile_json = json.load(profile_db)

    if not name in profile_json:
        log.warning(profile + ' does not have a slave named ' + name)
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

        profiles = []
        for file in os.listdir(config['dir']):
            if file.endswith('.json'):
                profiles.append(file[:-5])

        # count the number of slaves in each profile, and print.
        for prof in profiles:
            prof_file = os.path.join(config['dir'], prof + '.json')
            with open(prof_file, 'r') as profile_db:
                prof_json = json.load(profile_db)

            # add plural `s` if the profile has more than one slave
            slave_str = 'slave'
            if len(prof_json) > 1:
                slave_str += 's'

            print('* ' + prof + ' (' + str(len(prof_json)) + ' ' + slave_str + ')')
        return

    profile_file = _jackup_profile(config, profile)
    if not os.path.isfile(profile_file):
        log.warning('that profile does not exist')
        return

    with open(profile_file, 'r') as profile_db:
        profile_json = json.load(profile_db)

    table = [ ['name', 'source', 'destination', 'priority'] ]

    # sort the slaves by priority, from smallest to largest
    sorted_slaves = sorted(profile_json, key = lambda k: profile_json[k]['priority'])

    for slave in sorted_slaves:
        table.append([ slave, profile_json[slave]['source'],
                       profile_json[slave]['destination'],
                       str(profile_json[slave]['priority']) ])

    tp.print_table(table)

def _rsync(config, slave, src, dest, excludes=[]):
    """
    Wrapper for =rsync=, handles syncing SOURCE to DESTINATION.
    """
    rsync_args = ['--log-file=' + config['log'],
                  '--partial', '--progress', '--archive',
                  '--recursive', '--human-readable',
                  #'--timeout=30',
                  '--copy-links',
                  '--new-compress',
                  # '--checksum',
                  # '--quiet',
                  '--verbose',
                  # '--dry-run',
                  '--delete'
    ]

    # include the excludes as rsync ignore rules
    for ex in excludes:
        rsync_args += ['--exclude=' + ex]

    # call the `rsync` tool, capture errors and return them if any.
    cmd_rsync = subprocess.run(['rsync'] + rsync_args + [src, dest], stderr=subprocess.PIPE)
    rsync_stderr = str(cmd_rsync.stderr, 'utf-8', 'ignore').strip()
    return rsync_stderr

def _sync_slave(config, profile, slave, record):
    """
    Handles syncing a slaves SOURCE to its DESTINATION.
    Tries to parse the .jackupignore file if any, and then delegates syncing to
    `_rsync`.
    """
    log.success(slave + ": " + record['source'] + ' -> ' + record['destination'])

    # if a .jackupignore file exists, parse it
    excludes = []
    ignore_file = os.path.join(record['source'], '.jackupignore')
    if os.path.isfile(ignore_file):
        with open(ignore_file, 'r') as ignore_db:
            for line in ignore_db:
                excludes.append(line.strip())

    # try syncing the slave
    rsync_stderr = _rsync(config, slave, record['source'], record['destination'], excludes)

    # if any errors were found, log them and exit
    if rsync_stderr:
        log.error('failed syncing ' + profile + '/' + slave)
        log.error(rsync_stderr)
        return False

    log.success('completed syncing ' + profile + '/' + slave)
    return True

def sync(config, profile):
    """
    Synchronizes all slaves in PROFILE.
    """
    profile_file = _jackup_profile(config, profile)
    if not os.path.isfile(profile_file):
        log.error("That profile does not exist.")
        return

    lockfile = _jackup_profile_lock(config, profile)

    # only try syncing if we can lock the repository
    if os.path.isfile(lockfile):
        log.error("`jackup sync` is already running for this " + profile)
        return

    try:
        # create the lock when we acquire it
        open(lockfile, 'w').close()

        with open(profile_file, 'r') as profile_db:
            profile_json = json.load(profile_db)

        sorted_slaves = sorted(profile_json, key = lambda k: profile_json[k]['priority'])

        # keep count of how many slaves succeeded synchronizing
        syncs = 0

        # try syncing the slaves in order
        for slave in sorted_slaves:
            print('syncing ' + slave)
            if _sync_slave(config, profile, slave, profile_json[slave]):
                syncs += 1

        # done syncing, report statistics
        slave_count = str(syncs) + '/' + str(len(sorted_slaves))

        if syncs == 0 and len(sorted_slaves) > 0:
            slave_count = log.RED(slave_count)
        elif syncs < len(sorted_slaves):
            slave_count = log.YELLOW(slave_count)
        else:
            slave_count = log.GREEN(slave_count)

            print('synchronized ' + slave_count + " slaves")
            print('completed syncing ' + profile)
    except KeyboardInterrupt:
        log.warning("syncing interrupted by user.")
    finally:
        # free the lock for the profile
        os.remove(lockfile)
