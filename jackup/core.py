import os
import sys
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
        log.warning(f"the profile '{profile_name}' does not exist")
        return

    table = [["source", "destination"]]
    for task in prof.tasks(config, profile_name):
        table.append([task.source, task.destination])

    return table


def list(config: Config, profiles: List[str]) -> None:
    """
    If given a PROFILE, list all tasks in that profile, otherwise list all
    available profiles on the system.
    """
    if not profiles:
        log.info("profiles:")
        for profile in _list_available_profiles(config):
            print("* %s [%s]" % profile)

        return

    for profile in profiles:
        if not prof.exists(config, profile):
            log.error(f"the profile '{profile}' does not exist")
            continue

        log.info(f"profile: {profile}")
        if profile:
            tp.print_table(_list_profile(config, profile))
            print()


# TODO: move to own synchronizer backend
def _rsync(config: Config, src: str, dest: str, excludes=[]) -> str:
    """
    Wrapper for =rsync=, handles syncing SOURCE to DESTINATION.
    """
    rsync_args = [
        "--log-file=" + config.log_path,
        "--partial",
        # "--progress",
        # "--verbose",
        "--info=BACKUP,COPY,DEL,FLIST2,PROGRESS2,REMOVE,MISC2,STATS1,SYMSAFE",
        "--human-readable",
        # "--archive",  # -rlptgoD
        "--recursive",
        "--links",  # copy symlinks as symlinks
        "--perms",  # preserve permissions
        "--times",  # perserve modification times
        "--group",  # preserve group
        "--owner",  # preserve owner
        "--devices",  # preserve device files
        "--specials",  # preserve special files
        "--executability",  # preserve executability
        # "--xattrs",  # preserve extended attributes
        #'--timeout=30',
        # "--copy-links",  # transform links into the referent dirs/files
        # "--compress", # compress files during transfer
        "--new-compress",
        # '--checksum',
        # '--quiet',
        # '--dry-run'
        # '--delete' # add this as a per-entry setting
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
    ignore_file = os.path.join(folder, ".jackupignore")
    if os.path.isfile(ignore_file):
        with open(ignore_file, "r") as ignore_db:
            for line in ignore_db:
                excludes.append(line.strip())

    return excludes


def _sync_task(config: Config, task: Task) -> bool:
    """
    Tries to synchronize a task.
    """
    log.info(f"syncing {task.source} -> {task.destination}")

    # TODO: also pull in ignores from profile file
    excludes = _read_ignore_file(config, task.source)

    source = os.path.expanduser(task.source)
    destination = os.path.expanduser(task.destination)
    rsync_stderr = _rsync(config, source, destination, excludes, task.args)

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
            log.success(f"finished syncing {profile_name}/{task.name}\n")
            completed += 1
        else:
            log.error(f"failed syncing {profile_name}/{task.name}\n")

    return (completed, num_tasks)


# TODO: extract sync-logic, where rsync is a backend, maybe also support rclone, restic, etc.
def sync(config: Config, profiles: List[str], quiet: bool, verbose: bool) -> None:
    """
    Synchronizes all tasks in PROFILE.
    """
    if verbose:
        # SET LOG LEVEL VERBOSE
        print("VERBOSE")

    if quiet:
        # SET LOG LEVEL WARNINIG (quiet)
        print("quiet")

    for profile in profiles:
        if not prof.exists(config, profile):
            log.error(f"the profile '{profile}' does not exist")
            return

        if not prof.lock(config, profile):
            log.error(f"sync is already running for {profile}")
            return

        try:
            start_time = datetime.now()
            log.info(f"starting sync at {start_time}")
            (completed_tasks, total_tasks) = _sync_profile(config, profile)

            # report ratio of sucessful tasks to the total number of tasks,
            # color coded, based on success-rate of the synchronization
            task_ratio = f"{completed_tasks}/{total_tasks}"

            if completed_tasks == 0 and total_tasks > 0:
                task_ratio = log.RED(task_ratio)
            elif completed_tasks < total_tasks:
                task_ratio = log.YELLOW(task_ratio)
            else:
                task_ratio = log.GREEN(task_ratio)

            end_time = datetime.now()

            log.info(f"synchronized {task_ratio} tasks")
            log.info(f"finished syncing {profile}")
            log.info(f"sync ended at {end_time}, took {end_time - start_time}")
        except KeyboardInterrupt:
            log.warning("\n\nSynchronization interrupted by user")
        finally:
            prof.unlock(config, profile)
