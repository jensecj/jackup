import os
import json
import subprocess

import jackup.tableprinter as tp
import jackup.sysutils as su
import jackup.logging as log

def _path_to_profile(config, profile):
    """
    Returns the path to the profile-file belonging to PROFILE.
    """
    return os.path.join(config['dir'], profile + '.json')

def _profile_exists(config, profile):
    """
    Returns whether PROFILE exists.
    Is checked by the existence of the corresponding file in the jackup
    directory.
    """
    path = _path_to_profile(config, profile)
    return os.path.isfile(path)

def _path_to_profile_lock(config, profile):
    """
    Returns the path to the lockfile belonging to PROFILE.
    """
    return os.path.join(config['dir'], profile + '.lock')

def _lock_profile(config, profile):
    """
    Locks the specified PROFILE, so it can no longer be synchronized.
    """
    lockfile = _path_to_profile_lock(config, profile)

    if os.path.isfile(lockfile):
        return False

    open(lockfile, 'w').close()
    return True

def _unlock_profile(config, profile):
    """
    Unlocks the specified PROFILE, so that it can again be synchronized.
    """
    lockfile = _path_to_profile_lock(config, profile)
    if os.path.isfile(lockfile):
        os.remove(lockfile)

def _create_profile(config, profile):
    """
    Creates a new empty jackup profile.
    """
    path = _path_to_profile(config, profile)
    with open(path, 'w') as profile_db:
        json.dump({}, profile_db, indent=4)

def add(config, profile, name, source, destination, priority):
    """
    Add a new slave with NAME, to PROFILE.
    SOURCE/DESTINATION can be either local files/folders, or remote locations,
    accessible through ssh.
    PRIORITY is used to determine the order of synchronization, lower values
    get synchronized first.
    """
    if not _profile_exists(config, profile):
        print('profile does not exist, creating')
        _create_profile(config, profile)

    profile_file = _path_to_profile(config, profile)
    with open(profile_file, 'r') as profile_db:
        profile_json = json.load(profile_db)

    if name in profile_json:
        log.warning('This name is already in use')
        print('use `jackup edit <profile> <name>` to change settings inside this slave')
        return

    priorities = [ profile_json[slave]['priority'] for slave in profile_json ]
    if len(priorities) == 0:
        priorities += [0]

    # if we add a new slave without a priority, place it last in the queue of
    # slaves to synchronize by giving it the largest priority
    if not priority:
        priority = max(priorities) + 1

    # dont allow any slaves to have the same priorities
    if priority in priorities:
        log.warning("This priority is already used")
        return

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
    if not _profile_exists(config, profile):
        log.warning('that profile does not exist')
        return

    profile_file = _path_to_profile(config, profile)
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
    if not _profile_exists(config, profile):
        log.warning('that profile does not exist')
        return

    profile_file = _path_to_profile(config, profile)
    with open(profile_file, 'r') as profile_db:
        profile_json = json.load(profile_db)

    if not name in profile_json:
        log.warning(profile + ' does not have a slave named ' + name)
        return

    profile_json.pop(name)

    with open(profile_file, 'w') as profile_db:
        json.dump(profile_json, profile_db, indent=4)

    print("removed " + profile + '/' + name)

def _list_available_profiles(config):
    """
    List all available profiles on the system.
    """
    profiles = []
    for file in os.listdir(config['dir']):
        # all files in the jackup-directory ending with .json are profile-files
        if file.endswith('.json'):
            # when extracting the profiles name from the filename, do not
            # include the last 5 characters of the filename ('.json').
            profiles.append(file[:-5])

    print('Profiles:')
    # count the number of slaves in each profile, and print.
    for profile in profiles:
        profile_file = os.path.join(config['dir'], profile + '.json')
        with open(profile_file, 'r') as profile_db:
            slaves = json.load(profile_db)

        number_of_slaves = len(slaves)

        # add plural `s` if the profile has more than one slave
        slave_string = 'slave'
        if number_of_slaves > 1:
            slave_string += 's'

        print('* ' + profile + ' (' + str(number_of_slaves) + ' ' + slave_string + ')')

def _list_profile(config, profile):
    """
    List all slaves in a profile, their source, destination, and priority.
    The listing is sorted by order.
    """
    if not _profile_exists(config, profile):
        log.warning('that profile does not exist')
        return

    profile_file = _path_to_profile(config, profile)
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

def list(config, profile):
    """
    If given a PROFILE, list all slaves in that profile, otherwise list all
    available profiles on the system.
    """
    if profile:
        _list_profile(config, profile)
    else:
        _list_available_profiles(config)

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
    if not _profile_exists(config, profile):
        log.error("That profile does not exist.")
        return

    # create the lock when we acquire it
    if not _lock_profile(config, profile):
        log.error("`jackup sync` is already running for " + profile)
        return

    try:
        profile_file = _path_to_profile(config, profile)
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
        log.warning("\nsyncing interrupted by user.")
    finally:
        # free the lock for the profile
        _unlock_profile(config, profile)
