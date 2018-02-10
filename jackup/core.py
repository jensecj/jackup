import os
import json
import subprocess

import jackup.profile as prof
import jackup.logging as log
import jackup.tableprinter as tp

def add(config, profile_name, task_name, source, destination, order):
    """
    Add a new task with NAME, to PROFILE.
    SOURCE/DESTINATION can be either local files/folders, or remote locations,
    accessible through ssh.
    ORDER is used to determine the order of synchronization, lower values
    get synchronized first.
    """
    if not prof.exists(config, profile_name):
        log.info('Profile does not exist, creating...')
        prof.create(config, profile_name)

    profile = prof.read(config, profile_name)

    if task_name in profile:
        log.warning('That task already exists')
        log.info('Use `jackup edit <profile> <name>` to change settings for this task')
        return

    # if we add a new task without an order, place it last in the queue of
    # tasks to synchronize by giving it the largest order
    if not order:
        order = prof.max_order(profile) + 1

    orders = [ profile[task]['order'] for task in profile ]
    if order in orders:
        log.warning("That ordering is already in use")
        return

    profile[task_name] = { 'name': task_name, 'source': source, 'destination': destination, 'order': order }

    prof.write(config, profile_name, profile)

    log.info("added " + profile_name + '/' + task_name)

def edit(config, profile_name, task_name, source, destination, order):
    """
    Edit TASK, in PROFILE.
    Allows changing values of a task after creation.
    """
    if not prof.exists(config, profile_name):
        log.warning('That profile does not exist')
        return

    profile = prof.read(config, profile_name)

    if not task_name in profile:
        log.warning(profile_name + ' does not have a task named ' + task_name)
        return

    if source:
        profile[task_name]['source'] = source

    if destination:
        profile[task_name]['destination'] = destination

    if order:
        profile[task_name]['order'] = order

    prof.write(config, profile_name, profile)

    log.info("edited " + profile_name + '/' + task_name)

def remove(config, profile_name, task_name):
    """
    Remove an existing task with NAME, from PROFILE.
    """
    if not prof.exists(config, profile_name):
        log.warning('That profile does not exist')
        return

    profile = prof.read(config, profile_name)

    if not task_name in profile:
        log.warning(profile_name + ' does not have a task named ' + task_name)
        return

    profile.pop(task_name)

    prof.write(config, profile_name, profile)

    log.info("Removed " + profile_name + '/' + task_name)

def _list_available_profiles(config):
    """
    List all available profiles on the system.
    """
    log.info('Profiles:')

    for profile_name in prof.profiles(config):
        profile = prof.read(config, profile_name)

        number_of_tasks = len(profile)

        # add plural `s` if the profile has more than one task
        task_string = 'task'
        if number_of_tasks > 1:
            task_string += 's'

        log.info('* ' + profile_name + ' (' + str(number_of_tasks) + ' ' + task_string + ')')

def _list_profile(config, profile_name):
    """
    List all tasks in PROFILE, their source, destination, and order.
    The listing is sorted by order of synchronization.
    """
    if not prof.exists(config, profile_name):
        log.warning('That profile does not exist')
        return

    table = [ ['task', 'source', 'destination', 'order'] ]
    for task in prof.tasks(config, profile_name):
        table.append([ task['name'],
                       task['source'],
                       task['destination'],
                       str(task['order']) ])

    tp.print_table(table)

def list(config, profile_name):
    """
    If given a PROFILE, list all tasks in that profile, otherwise list all
    available profiles on the system.
    """
    if profile_name:
        _list_profile(config, profile_name)
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

def _read_ignore_file(config, folder):
    """
    Reads the .jackupignore file, if any, from a folder
    """
    excludes = []
    ignore_file = os.path.join(os.path.dirname(folder), '.jackupignore')
    if os.path.isfile(ignore_file):
        with open(ignore_file, 'r') as ignore_db:
            for line in ignore_db:
                excludes.append(line.strip())

    return excludes

def _sync_task(config, task):
    """
    Tries to synchronize a task.
    """
    log.info('Syncing ' + task['name'] + ": " + task['source'] + ' -> ' + task['destination'])

    excludes = _read_ignore_file(config, task['source'])
    rsync_stderr = _rsync(config, task['source'], task['destination'], excludes)

    if rsync_stderr:
        log.error(rsync_stderr)
        return False
    else:
        return True

def _sync_profile(config, profile_name):
    """
    Tries to synchronize all tasks in PROFILE.
    Returns a tuple of successful tasks, and total tasks.
    """
    profile = prof.read(config, profile_name)

    completed = 0
    for task in prof.tasks(config, profile_name):
        if _sync_task(config, task):
            log.success('Completed syncing ' + profile_name + '/' + task['name'])
            completed += 1
        else:
            log.error('Failed syncing ' + profile_name + '/' + task['name'])

    return (completed, len(profile))

def sync(config, profile_name):
    """
    Synchronizes all tasks in PROFILE.
    """
    if not prof.exists(config, profile_name):
        log.error("That profile does not exist")
        return

    if not prof.lock(config, profile_name):
        log.error("`jackup sync` is already running for " + profile_name)
        return

    try:
        (completed_tasks, total_tasks) = _sync_profile(config, profile_name)

        # report ratio of sucessful tasks to the total number of tasks,
        # color coded, based on success-rate of the synchronization
        task_ratio = str(completed_tasks) + '/' + str(total_tasks)

        if completed_tasks == 0 and total_tasks > 0:
            task_ratio = log.RED(task_ratio)
        elif completed_tasks < total_tasks:
            task_ratio = log.YELLOW(task_ratio)
        else:
            task_ratio = log.GREEN(task_ratio)

        log.info('Synchronized ' + task_ratio + " tasks")
        log.info('Completed syncing ' + profile_name)
    except KeyboardInterrupt:
        log.warning("\nSynchronization interrupted by user")
    finally:
        prof.unlock(config, profile_name)
