import os
import sys
import json
import subprocess

from datetime import datetime
from typing import List, Tuple, Optional

from jackup.profile import Profile
from jackup.task import Task

import jackup.profile as prof
import jackup.log as log
import jackup.tableprinter as tp


def _list_available_profiles(config) -> List[Tuple[str, str]]:
    """
    List all available profiles on the system.
    """
    profiles = []
    for profile_name in prof.profiles(config):
        number_of_tasks = len(prof.tasks(config, profile_name))
        profiles.append((profile_name, str(number_of_tasks)))

    return profiles


def _list_profile(config, profile_name: str):
    """
    List all tasks in PROFILE, their source, destination.
    The listing is sorted by order of synchronization.
    """
    if not prof.exists(config, profile_name):
        log.warning(f"the profile '{profile_name}' does not exist")
        return

    table = [["source", "destination", "args"]]
    for task in prof.tasks(config, profile_name):
        args = " ".join(task.args)
        table.append([task.src, task.dest, args])

    return table


def list(config, profiles: List[str]) -> None:
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
def _rsync(config, src: str, dest: str, args: List[str] = []) -> str:
    """
    Wrapper for =rsync=, handles syncing SRC to DEST.
    """
    rsync_args = [
        "--log-file=" + config.log_path,
        # print number of files, bytes sent/recieved, throughput, and total size
        "--info=BACKUP,COPY,DEL,FLIST2,PROGRESS2,REMOVE,MISC2,STATS1,SYMSAFE",
        "--no-motd",
        # "--timeout=30",
        "--partial",
        "--progress",
        "--human-readable",
        "--archive",  # -rlptgoD
        # "--recursive", # -r
        # "--links",  # -l, copy symlinks as symlinks
        # "--perms",  # -p, preserve permissions
        # "--times",  # -t, perserve modification times
        # "--group",  # -g, preserve group
        # "--owner",  # -o, preserve owner
        # "--devices",  # -D, preserve device files (superuser only)
        # "--specials",  # -D, preserve special files
        "--executability",  # preserve executability
        "--xattrs",  # preserve extended attributes
        "--acls",  # preserve ACLS
        # "--copy-links",  # transform links into the referent dirs/files
        "--compress",  # compress files during transfer
        # "--dry-run",
    ]

    rsync_args += args
    log.debug(f"rsync {rsync_args} {src} {dest}")

    # call the `rsync` tool, capture errors and return them if any.
    cmd_rsync = subprocess.run(
        ["rsync"] + rsync_args + [src, dest], stderr=subprocess.PIPE
    )
    rsync_stderr = str(cmd_rsync.stderr, "utf-8", "ignore").strip()
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


def _sync_task(config, task: Task) -> bool:
    """
    Tries to synchronize a task.
    """
    log.info(f"syncing {task.src} -> {task.dest}")

    # TODO: also pull in ignores from profile file
    excludes = _read_ignore_file(config, task.src)

    source = os.path.expanduser(task.src)
    destination = os.path.expanduser(task.dest)

    args = task.args

    for ex in excludes:
        args += ["--exclude=" + ex]

    if log.LOG_LEVEL < log.LEVEL.INFO:
        args += ["--quiet"]
    elif log.LOG_LEVEL > log.LEVEL.INFO:
        args += ["--verbose"]

    rsync_stderr = _rsync(config, source, destination, args)

    if rsync_stderr:
        log.error(rsync_stderr)
        return False
    else:
        return True


def _sync_profile(config, profile_name: str) -> Tuple[int, int]:
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
def _sync(config, profile: str) -> bool:
    if not prof.exists(config, profile):
        log.error(f"the profile '{profile}' does not exist")
        return False

    if not prof.lock(config, profile):
        log.error(f"sync is already running for {profile}")
        return False

    try:
        start_time = datetime.now()
        log.info(f"starting sync at {start_time}")
        (completed_tasks, total_tasks) = _sync_profile(config, profile)
        end_time = datetime.now()

        # report ratio of sucessful tasks to the total number of tasks,
        # color coded, based on success-rate of the synchronization
        task_ratio = f"{completed_tasks}/{total_tasks}"

        if completed_tasks == 0 and total_tasks > 0:
            task_ratio = log.RED(task_ratio)
        elif completed_tasks < total_tasks:
            task_ratio = log.YELLOW(task_ratio)
        else:
            task_ratio = log.GREEN(task_ratio)

        log.info(f"synchronized {task_ratio} tasks")
        log.info(f"finished syncing {profile}")
        log.info(f"sync ended at {end_time}, took {end_time - start_time}")

        return completed_tasks == total_tasks
    except KeyboardInterrupt:
        log.warning("\n\nSynchronization interrupted by user")
    finally:
        prof.unlock(config, profile)


def sync(config, profiles: List[str], quiet: bool, verbose: bool) -> None:
    """
    Synchronizes all tasks in PROFILE.
    """
    if verbose:
        log.set_level(log.LEVEL.DEBUG)

    if quiet:
        log.set_level(log.LEVEL.WARNING)

    failures = 0
    for profile in profiles:
        if not _sync(config, profile):
            log.warning(f"{profile} failed to sync")
            failures += 1

    if failures == 0:
        log.success("all profiles synchronized successfully")
    else:
        log.warning(f"{failures} profile(s) failed to sync all tasks")
