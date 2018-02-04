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

def _create_profile(config, profile):
    """
    Creates a new empty jackup profile, with the given name.
    """
    path = _path_to_profile(config, profile)
    with open(path, 'w') as profile_db:
        json.dump({}, profile_db, indent=4)

def _read_profile(config, profile):
    """
    Reads the content of the profile-file from disk, and returns it.
    """
    profile_file = _path_to_profile(config, profile)
    with open(profile_file, 'r') as profile_db:
        tasks = json.load(profile_db)

    return tasks

def _write_profile(config, profile, content):
    """
    Writes new content to the profile-file on disk.
    """
    profile_file = _path_to_profile(config, profile)
    with open(profile_file, 'w') as profile_db:
        json.dump(content, profile_db, indent=4)

def _path_to_profile_lock(config, profile):
    """
    Returns the path to the lockfile belonging to PROFILE.
    """
    return os.path.join(config['dir'], profile + '.lock')

def _lock_profile(config, profile):
    """
    Locks the specified PROFILE, so it can no longer be synchronized.
    Returns True if profile was locked successfully,
    returns False if the profile was already locked.
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

def _sort_tasks_by_order(config, profile):
    tasks = _read_profile(config, profile)
    return sorted(tasks, key = lambda k: tasks[k]['priority'])

def add(config, profile, task, source, destination, priority):
    """
    Add a new task with NAME, to PROFILE.
    SOURCE/DESTINATION can be either local files/folders, or remote locations,
    accessible through ssh.
    PRIORITY is used to determine the order of synchronization, lower values
    get synchronized first.
    """
    if not _profile_exists(config, profile):
        log.info('profile does not exist, creating')
        _create_profile(config, profile)

    tasks = _read_profile(config, profile)

    if task in tasks:
        log.warning('This name is already in use')
        log.info('use `jackup edit <profile> <name>` to change settings for this task')
        return

    priorities = [ tasks[t]['priority'] for t in tasks ]
    if len(priorities) == 0:
        priorities += [0]

    # if we add a new task without a priority, place it last in the queue of
    # tasks to synchronize by giving it the largest priority
    if not priority:
        priority = max(priorities) + 1

    # dont allow any tasks to have the same priorities
    if priority in priorities:
        log.warning("This priority is already used")
        return

    # the record kept for each task in the profile
    tasks[task] = { 'source': source, 'destination': destination, 'priority': priority }

    _write_profile(config, profile, tasks)

    log.info("added " + profile + '/' + task)

def edit(config, profile, task, source, destination, priority):
    """
    Edit TASK, in PROFILE.
    Allows changing values of a task after creation.
    """
    if not _profile_exists(config, profile):
        log.warning('that profile does not exist')
        return

    tasks = _read_profile(config, profile)

    if not task in tasks:
        log.warning(profile + ' does not have a task named ' + task)
        return

    if source:
        tasks[task]['source'] = source

    if destination:
        tasks[task]['destination'] = destination

    if priority:
        tasks[task]['priority'] = priority

    _write_profile(config, profile, tasks)

    log.info("edited " + profile + '/' + task)

def remove(config, profile, task):
    """
    Remove an existing task with NAME, from PROFILE.
    """
    if not _profile_exists(config, profile):
        log.warning('that profile does not exist')
        return

    tasks = _read_profile(config, profile)

    if not task in tasks:
        log.warning(profile + ' does not have a task named ' + task)
        return

    tasks.pop(task)

    _write_profile(config, profile, tasks)

    log.info("removed " + profile + '/' + task)

def _get_available_profiles(config):
    """
    Get the names of all available profiles on the system.
    This is done by finding all profile-files (files ending in .json) in the
    jackup directory.
    """
    profiles = [ profile[:-5] # dont include the last 5 charaters of the filename ('.json')
                 for profile
                 in os.listdir(config['dir']) # list all files in the jackup directory
                 if profile.endswith('.json') ] # that end with '.json', these are the profiles
    return profiles

def _list_available_profiles(config):
    """
    List all available profiles on the system.
    """
    log.info('Profiles:')
    # count the number of tasks in each profile, and print.
    for profile in _get_available_profiles(config):
        tasks = _read_profile(config, profile)

        number_of_tasks = len(tasks)

        # add plural `s` if the profile has more than one task
        task_string = 'task'
        if number_of_tasks > 1:
            task_string += 's'

        log.info('* ' + profile + ' (' + str(number_of_tasks) + ' ' + task_string + ')')

def _list_profile(config, profile):
    """
    List all tasks in a profile, their source, destination, and priority.
    The listing is sorted by order.
    """
    if not _profile_exists(config, profile):
        log.warning('that profile does not exist')
        return

    tasks = _read_profile(config, profile)

    table = [ ['task', 'source', 'destination', 'priority'] ]

    # sort the tasks by priority, from smallest to largest
    sorted_tasks = _sort_tasks_by_order(config, profile)

    for task in sorted_tasks:
        table.append([ task,
                       tasks[task]['source'],
                       tasks[task]['destination'],
                       str(tasks[task]['priority']) ])

    tp.print_table(table)

def list(config, profile):
    """
    If given a PROFILE, list all tasks in that profile, otherwise list all
    available profiles on the system.
    """
    if profile:
        _list_profile(config, profile)
    else:
        _list_available_profiles(config)

def _rsync(config, task, src, dest, excludes=[]):
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

def _sync_task(config, profile, task, record):
    """
    Handles syncing a tasks SOURCE to its DESTINATION.
    Tries to parse the .jackupignore file if any, and then delegates syncing to
    `_rsync`.
    """
    log.success(task + ": " + record['source'] + ' -> ' + record['destination'])

    # if a .jackupignore file exists, parse it
    excludes = []
    ignore_file = os.path.join(record['source'], '.jackupignore')
    if os.path.isfile(ignore_file):
        with open(ignore_file, 'r') as ignore_db:
            for line in ignore_db:
                excludes.append(line.strip())

    # try syncing the task
    rsync_stderr = _rsync(config, task, record['source'], record['destination'], excludes)

    # if any errors were found, log them and exit
    if rsync_stderr:
        log.error('failed syncing ' + profile + '/' + task)
        log.error(rsync_stderr)
        return False

    log.success('completed syncing ' + profile + '/' + task)
    return True

def sync(config, profile):
    """
    Synchronizes all tasks in PROFILE.
    """
    if not _profile_exists(config, profile):
        log.error("That profile does not exist.")
        return

    if not _lock_profile(config, profile):
        log.error("`jackup sync` is already running for " + profile)
        return

    try:
        tasks = _read_profile(config, profile)
        sorted_tasks = _sort_tasks_by_order(config, profile)

        # keep count of how many tasks succeeded synchronizing
        syncs = 0

        # try syncing the tasks in order
        for task in sorted_tasks:
            log.info('syncing ' + task)
            if _sync_task(config, profile, task, tasks[task]):
                syncs += 1

        # done syncing, report statistics
        task_count = str(syncs) + '/' + str(len(sorted_tasks))

        if syncs == 0 and len(sorted_tasks) > 0:
            task_count = log.RED(task_count)
        elif syncs < len(sorted_tasks):
            task_count = log.YELLOW(task_count)
        else:
            task_count = log.GREEN(task_count)

            log.info('synchronized ' + task_count + " tasks")
            log.info('completed syncing ' + profile)
    except KeyboardInterrupt:
        log.warning("\nsyncing interrupted by user.")
    finally:
        # free the lock for the profile
        _unlock_profile(config, profile)
