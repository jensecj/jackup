import os
import json
import subprocess

import jackup.sysutils as su
import jackup.profile as prof
import jackup.logging as log
import jackup.tableprinter as tp

def _new_highest_order(tasks):
    """
    Get the highest order of any task in TASKS
    """
    # if there are no tasks in the profile, the new ordering starts at 1.
    if len(tasks) == 0:
        return 1

    orders = [ tasks[t]['order'] for t in tasks ]
    return max(orders) + 1

def add(config, profile_name, task_name, source, destination, order):
    """
    Add a new task with NAME, to PROFILE.
    SOURCE/DESTINATION can be either local files/folders, or remote locations,
    accessible through ssh.
    ORDER is used to determine the order of synchronization, lower values
    get synchronized first.
    """
    if not prof.exists(config, profile_name):
        log.info('profile does not exist, creating')
        prof.create(config, profile_name)

    tasks = prof.read(config, profile_name)

    if task_name in tasks:
        log.warning('This name is already in use')
        log.info('use `jackup edit <profile> <name>` to change settings for this task')
        return

    # if we add a new task without an order, place it last in the queue of
    # tasks to synchronize by giving it the largest order
    if not order:
        order = _new_highest_order(tasks)

    orders = [ tasks[t]['order'] for t in tasks ]
    if order in orders:
        log.warning("This order is already used")
        return

    tasks[task_name] = { 'source': source, 'destination': destination, 'order': order }

    prof.write(config, profile_name, tasks)

    log.info("added " + profile_name + '/' + task_name)

def edit(config, profile_name, task_name, source, destination, order):
    """
    Edit TASK, in PROFILE.
    Allows changing values of a task after creation.
    """
    if not prof.exists(config, profile_name):
        log.warning('that profile does not exist')
        return

    tasks = prof.read(config, profile_name)

    if not task_name in tasks:
        log.warning(profile_name + ' does not have a task named ' + task_name)
        return

    if source:
        tasks[task_name]['source'] = source

    if destination:
        tasks[task_name]['destination'] = destination

    if order:
        tasks[task_name]['order'] = order

    prof.write(config, profile_name, tasks)

    log.info("edited " + profile_name + '/' + task_name)

def remove(config, profile_name, task_name):
    """
    Remove an existing task with NAME, from PROFILE.
    """
    if not prof.exists(config, profile_name):
        log.warning('that profile does not exist')
        return

    tasks = prof.read(config, profile_name)

    if not task_name in tasks:
        log.warning(profile_name + ' does not have a task named ' + task_name)
        return

    tasks.pop(task_name)

    prof.write(config, profile_name, tasks)

    log.info("removed " + profile_name + '/' + task_name)

def _list_available_profiles(config):
    """
    List all available profiles on the system.
    """
    log.info('Profiles:')

    for profile in prof.available_profiles(config):
        tasks = prof.read(config, profile)

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

def _list_profile(config, profile_name):
    """
    List all tasks in PROFILE, their source, destination, and order.
    The listing is sorted by order of synchronization.
    """
    if not prof.exists(config, profile_name):
        log.warning('that profile does not exist')
        return

    tasks = prof.read(config, profile_name)
    sorted_task_ids = _sort_task_ids_by_order(tasks)

    table = [ ['task', 'source', 'destination', 'order'] ]
    for task in sorted_task_ids:
        table.append([ task,
                       tasks[task]['source'],
                       tasks[task]['destination'],
                       str(tasks[task]['order']) ])

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

def _read_ignore_file(config, profile_name, task_name):
    """
    Reads the .jackupignore file, if any, from a tasks source
    """
    tasks = prof.read(config, profile_name)
    folder = os.path.dirname(tasks[task_name]['source'])

    excludes = []
    ignore_file = os.path.join(folder, '.jackupignore')
    if os.path.isfile(ignore_file):
        with open(ignore_file, 'r') as ignore_db:
            for line in ignore_db:
                excludes.append(line.strip())

    return excludes

def _sync_task(config, profile_name, task_name):
    """
    Tries to synchronize a task.
    """
    tasks = prof.read(config, profile_name)

    log.info('syncing ' + task_name + ": " + tasks[task_name]['source'] + ' -> ' + tasks[task_name]['destination'])

    excludes = _read_ignore_file(config, profile_name, task_name)
    rsync_stderr = _rsync(config, tasks[task_name]['source'], tasks[task_name]['destination'], excludes)

    if rsync_stderr:
        log.error('failed syncing ' + profile_name + '/' + task_name)
        log.error(rsync_stderr)
        return False

    log.success('completed syncing ' + profile_name + '/' + task_name)
    return True

def _sync_profile(config, profile_name):
    """
    Tries to synchronize all tasks in PROFILE.
    Returns a tuple of successful tasks, and total tasks.
    """
    tasks = prof.read(config, profile_name)
    sorted_task_ids = _sort_task_ids_by_order(tasks)

    completed = 0
    for task_id in sorted_task_ids:
        if _sync_task(config, profile_name, task_id):
            completed += 1

    return (completed, len(tasks))

def sync(config, profile_name):
    """
    Synchronizes all tasks in PROFILE.
    """
    if not prof.exists(config, profile_name):
        log.error("That profile does not exist.")
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

        log.info('synchronized ' + task_ratio + " tasks")
        log.info('completed syncing ' + profile_name)
    except KeyboardInterrupt:
        log.warning("\nsyncing interrupted by user.")
    finally:
        prof.unlock(config, profile_name)
