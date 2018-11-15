import os
import json
import subprocess

from datetime import datetime
from typing import List, Tuple, Optional

from jackup.profile import Profile
from jackup.task import Task
from jackup.config import Config

import jackup.profile as prof
import jackup.logging as log
import jackup.tableprinter as tp

def _add(config: Config, profile: Profile, task: Task) -> Optional[Profile]:
    if task.name in [ t.name for t in profile.tasks ]:
        log.warning('That task already exists')
        log.info('Use `jackup edit <profile> <name>` to change settings for this task')
        return None

    new_task = task

    # if we add a new task without an order, place it last in the queue of
    # tasks to synchronize by giving it the latest order
    if new_task.order is None:
        new_task = Task(task.name,
                        task.source,
                        task.destination,
                        prof.max_order(profile.tasks) + 1)

    if task.order in prof.orders(profile.tasks):
        log.warning("That ordering is already in use")
        log.info('Use `jackup list <profile>` to check ordering of tasks')
        return None

    new_profile = prof.add(profile, new_task)
    return new_profile

def add(config: Config, profile_name: str, task_name: str, source: str, destination: str, order: int) -> None:
    """
    Add a new task with NAME, to PROFILE.
    SOURCE/DESTINATION can be either local files/folders, or remote locations,
    accessible through ssh.
    ORDER is used to determine the order of synchronization, lower values
    get synchronized first.
    """
    task = Task(task_name, source, destination, order)
    profile = prof.get_profile_by_name(config, profile_name)

    # TODO: extract profile from profile_name, and pass to _add
    new_profile = _add(config, profile, task)

    if new_profile is not None:
        prof.write(config, profile.name, prof.toJSON(new_profile))
        log.info("added " + profile.name + '/' + task.name)

def edit(config: Config, profile_name: str, task_name: str, source: str, destination: str, order: int) -> None:
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

def remove(config: Config, profile_name: str, task_name: str) -> None:
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

def _list_available_profiles(config: Config) -> List[Tuple[str, str]]:
    """
    List all available profiles on the system.
    """
    profiles = []
    for profile_name in prof.profiles(config):
        number_of_tasks = len(prof.tasks(config, profile_name))

        profiles.append((profile_name, str(number_of_tasks)))

    return profiles

def _list_profile(config: Config, profile_name: str):
    """
    List all tasks in PROFILE, their source, destination, and order.
    The listing is sorted by order of synchronization.
    """
    if not prof.exists(config, profile_name):
        log.warning('That profile does not exist')
        return

    table = [ ['task', 'source', 'destination', 'order'] ]
    for task in prof.tasks(config, profile_name):
        table.append([ task.name,
                       task.source,
                       task.destination,
                       str(task.order) ])

    return table

def list(config: Config, profile_name: str) -> None:
    """
    If given a PROFILE, list all tasks in that profile, otherwise list all
    available profiles on the system.
    """
    if profile_name:
        tp.print_table(_list_profile(config, profile_name))
    else:
        log.info('Profiles:')
        for profile in _list_available_profiles(config):
            print("* %s [%s]" % profile)

# TODO: maybe use rclone instead of rsync?
def _rsync(config: Config, source: str, destination: str, excludes=[]) -> str:
    """
    Wrapper for =rsync=, handles syncing SOURCE to DESTINATION.
    """
    rsync_args = ['--log-file=' + config.log_path,
                  '--partial', '--progress', '--archive',
                  '--recursive', '--human-readable',
                  #'--timeout=30',
                  '--copy-links',
                  '--new-compress',
                  # '--checksum',
                  # '--quiet',
                  '--verbose',
                  # '--dry-run'
                  # '--delete'
    ]

    for ex in excludes:
        rsync_args += ['--exclude=' + ex]

    # call the `rsync` tool, capture errors and return them if any.
    cmd_rsync = subprocess.run(['rsync'] + rsync_args + [source, destination], stderr=subprocess.PIPE)
    rsync_stderr = str(cmd_rsync.stderr, 'utf-8', 'ignore').strip()
    return rsync_stderr

def _read_ignore_file(config: Config, folder: str) -> List[str]:
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

def _sync_task(config: Config, task) -> bool:
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

def _sync_profile(config: Config, profile_name: str) -> Tuple[int, int]:
    """
    Tries to synchronize all tasks in PROFILE.
    Returns a tuple of successful tasks, and total tasks.
    """
    num_tasks = len(prof.read(config, profile_name))
    completed = 0
    for task in prof.tasks(config, profile_name):
        if _sync_task(config, task):
            log.success('Completed syncing ' + profile_name + '/' + task['name'])
            completed += 1
        else:
            log.error('Failed syncing ' + profile_name + '/' + task['name'])

    return (completed, num_tasks)

def sync(config: Config, profile_name: str) -> None:
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
        start_time = datetime.now()
        log.info("Starting sync at " + str(start_time))
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

        end_time = datetime.now()

        log.info('Synchronized ' + task_ratio + " tasks")
        log.info('Completed syncing ' + profile_name)
        log.info("Synching ended at " + str(end_time) + ", took " + str(end_time - start_time))
    except KeyboardInterrupt:
        log.warning("\nSynchronization interrupted by user")
    finally:
        prof.unlock(config, profile_name)
