import os
import json
import subprocess

import jackup.sysutils as su
import jackup.logging as log
import jackup.tableprinter as tp

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

def _new_highest_order(tasks):
    """
    Get the highest order of any task in TASKS
    """
    # if there are no tasks in the profile, the new ordering starts at 1.
    if len(tasks) == 0:
        return 1

    orders = [ tasks[t]['order'] for t in tasks ]
    return max(orders) + 1

def add(config, profile, task, source, destination, order):
    """
    Add a new task with NAME, to PROFILE.
    SOURCE/DESTINATION can be either local files/folders, or remote locations,
    accessible through ssh.
    ORDER is used to determine the order of synchronization, lower values
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

    # if we add a new task without an order, place it last in the queue of
    # tasks to synchronize by giving it the largest order
    if not order:
        order = _new_highest_order(tasks)

    if order in orders:
        log.warning("This order is already used")
        return

    tasks[task] = { 'source': source, 'destination': destination, 'order': order }

    _write_profile(config, profile, tasks)

    log.info("added " + profile + '/' + task)

def edit(config, profile, task, source, destination, order):
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

    if order:
        tasks[task]['order'] = order

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

    for profile in _get_available_profiles(config):
        tasks = _read_profile(config, profile)

        number_of_tasks = len(tasks)

        # add plural `s` if the profile has more than one task
        task_string = 'task'
        if number_of_tasks > 1:
            task_string += 's'

        log.info('* ' + profile + ' (' + str(number_of_tasks) + ' ' + task_string + ')')

def _sort_task_ids_by_order(tasks):
    """
    Returns a list of task ids from PROTILE, sorted by the order in which they will
    be synchronized.
    """
    return sorted(tasks, key = lambda k: tasks[k]['order'])

def _list_profile(config, profile):
    """
    List all tasks in PROFILE, their source, destination, and order.
    The listing is sorted by order of synchronization.
    """
    if not _profile_exists(config, profile):
        log.warning('that profile does not exist')
        return

    tasks = _read_profile(config, profile)
    sorted_task_ids = _sort_task_ids_by_order(tasks)

    table = [ ['task', 'source', 'destination', 'order'] ]
    for task in sorted_task_ids:
        table.append([ task,
                       tasks[task]['source'],
                       tasks[task]['destination'],
                       str(tasks[task]['order']) ])

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

def _rsync(config, source, destination, excludes=[]):
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

    for ex in excludes:
        rsync_args += ['--exclude=' + ex]

    # call the `rsync` tool, capture errors and return them if any.
    cmd_rsync = subprocess.run(['rsync'] + rsync_args + [source, destination], stderr=subprocess.PIPE)
    rsync_stderr = str(cmd_rsync.stderr, 'utf-8', 'ignore').strip()
    return rsync_stderr

def _read_ignore_file(config, profile, task):
    """
    Reads the .jackupignore file, if any, from a tasks source
    """
    tasks = _read_profile(config, profile)
    folder = os.path.dirname(tasks[task]['source'])

    excludes = []
    ignore_file = os.path.join(folder, '.jackupignore')
    if os.path.isfile(ignore_file):
        with open(ignore_file, 'r') as ignore_db:
            for line in ignore_db:
                excludes.append(line.strip())

    return excludes

def _sync_task(config, profile, task):
    """
    Tries to synchronize a task.
    """
    tasks = _read_profile(config, profile)

    log.info('syncing ' + task + ": " + tasks[task]['source'] + ' -> ' + tasks[task]['destination'])

    excludes = _read_ignore_file(config, profile, task)
    rsync_stderr = _rsync(config, tasks[task]['source'], tasks[task]['destination'], excludes)

    if rsync_stderr:
        log.error('failed syncing ' + profile + '/' + task)
        log.error(rsync_stderr)
        return False

    log.success('completed syncing ' + profile + '/' + task)
    return True

def _sync_profile(config, profile):
    """
    Tries to synchronize all tasks in PROFILE.
    Returns a tuple of successful tasks, and total tasks.
    """
    tasks = _read_profile(config, profile)
    sorted_task_ids = _sort_task_ids_by_order(tasks)

    completed = 0
    for task_id in sorted_task_ids:
        if _sync_task(config, profile, task_id):
            completed += 1

    return (completed, len(tasks))

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
        (completed_tasks, total_tasks) = _sync_profile(config, profile)

        # report ratio of sucessful tasks to the total number of tasks,
        # color coded, based on success-rate of the synchronization
        task_ratio = str(completed_tasks) + '/' + str(total_tasks)

        if completed_tasks == 0 and total_tasks > 0:
            task_ratio = log.RED(task_ratio)
        elif completed_tasks < total_tasks:
            task_ratio = log.YELLOW(task_ratio)
        else:
            task_ratio = log.GREEN(task_ratio)

        log.info('synchronized ' + task_ratio + " tasks")
        log.info('completed syncing ' + profile)
    except KeyboardInterrupt:
        log.warning("\nsyncing interrupted by user.")
    finally:
        _unlock_profile(config, profile)
