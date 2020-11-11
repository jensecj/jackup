import os
import sys
import json
import subprocess
import logging

from typing import List, Tuple, Optional

from . import profile as prof
from . import utils
from .utils import time
from .config import CONFIG

log = logging.getLogger(__name__)


def _get_available_profiles() -> List[Tuple[str, str]]:
    profiles = []
    for profile in prof.profiles():
        number_of_tasks = len(prof.tasks(profile))
        profiles.append((profile, number_of_tasks))

    return profiles


def _print_available_profiles() -> None:
    """
    List all available profiles on the system.
    """
    log.info("profiles:")
    for profile in _get_available_profiles():
        log.info("- %s [%s]" % profile)


def _print_profile(profile: str) -> None:
    """
    List all tasks in PROFILE, their source, destination.
    The listing is sorted by order of synchronization.
    """
    headings = ["source", "destination", "args"]
    table = []
    for task in prof.tasks(profile):
        args = " ".join(task.args)
        table.append([task.src, task.dest, args])

    log.info(f"profile: {profile}")
    utils.print_table(headings, table)


def list(profiles: List[str]) -> None:
    """
    If given a PROFILE, list all tasks in that profile, otherwise list all
    available profiles on the system.
    """
    if not profiles:
        _print_available_profiles()
        return

    for profile in profiles:
        if not prof.exists(profile):
            log.error(f"the profile '{profile}' does not exist")
            continue

        if profile:
            _print_profile(profile)


def _read_ignore_file(folder: str) -> List[str]:
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


# TODO: move to own synchronizer backend
def _rsync(src: str, dest: str, args: List[str] = []) -> bool:
    rsync_args = [
        "--log-file=" + CONFIG.get("log_path"),
        "--no-motd",
        "--compress",  # compress files during transfer
        # "--timeout=30",
        "--partial",
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
        # "--dry-run",
    ]

    rsync_args += args

    # make sure we dont expand filenames into args
    rsync_cmd = ["rsync"] + rsync_args + ["--"] + [src] + [dest]

    # capture errors and return them if any.
    with subprocess.Popen(rsync_cmd, stderr=subprocess.PIPE, text=True) as p:
        if return_code := p.wait():
            log.error(f"rsync failed to sync, returned {return_code}")

        if rsync_stderr := p.stderr.read().strip():
            log.error(rsync_stderr)

        return return_code == 0


def _sync_rsync(task) -> bool:
    source = os.path.expanduser(task.src)
    destination = os.path.expanduser(task.dest)

    # TODO: validate paths, error on connection error, unmounted, not-found
    if not os.path.exists(source):
        log.error(f"{source} does not exist")
        return False

    if not os.path.exists(destination):
        log.error(f"{destination} does not exist")
        return False

    if task.src_mounted and not os.path.ismount(source):
        log.error(f"{source} is not mounted")
        return False

    if task.dest_mounted and not os.path.ismount(destination):
        log.error(f"{destination} is not mounted")
        return False

    # TODO: translate paths, from uuid, network-shares, etc.

    args = task.args[:]  # copy list so we dont keep appending args

    # TODO: also ignore directories which contain a beacon-file (e.g. .rsyncignore)
    excludes = _read_ignore_file(source)

    for ex in excludes:
        args += ["--exclude=" + ex]

    # TODO: fix verbosity
    # if log.LOG_LEVEL < log.LEVEL.INFO:
    #     args += ["--quiet"]
    # elif log.LOG_LEVEL > log.LEVEL.INFO:

    verbosity = {
        0: ["--quiet"],
        1: [
            "--progress",
            "--info=BACKUP,COPY,DEL,FLIST2,PROGRESS2,REMOVE,MISC2,STATS1,SYMSAFE",
        ],
        # print number of files, bytes sent/recieved, throughput, and total size
        2: [
            "--progress",
            "--info=BACKUP,COPY,DEL,FLIST2,PROGRESS2,REMOVE,MISC2,STATS1,SYMSAFE",
            "--verbose",
        ],
    }

    args += verbosity.get(CONFIG.get("verbosity"))

    return _rsync(source, destination, args)


# TODO: extract sync-logic, where rsync is a backend, maybe also support rclone, restic, etc.
def _sync_task(task) -> bool:
    log.info(f"● syncing {task.src} -> {task.dest}")

    # TODO: dispatch on type of sync: borg, rsync, rclone, etc.
    return _sync_rsync(task)


def _sync_profile(profile: str) -> Tuple[int, int]:
    """
    Tries to synchronize all tasks in PROFILE.
    Returns a tuple of successful tasks, and total tasks.
    """
    num_tasks = len(prof.load(profile))
    completed = 0

    # TODO: sync profiles in parallel? with `-j N' arg?
    for task in prof.tasks(profile):
        if _sync_task(task):
            completed += 1
            log.info(f"finished syncing {profile}/{task.name}")
        else:
            log.error(f"failed to sync {profile}/{task.name}")

    return (completed, num_tasks)


@time
def _sync(profile: str) -> bool:
    if not prof.exists(profile):
        log.error(f"the profile '{profile}' does not exist")
        return

    if not prof.lock(profile):
        log.error(f"sync is already running for {profile}")
        return

    try:
        return _sync_profile(profile)
    finally:
        prof.unlock(profile)


def sync(profiles: List[str]) -> None:
    """
    Synchronizes all tasks in PROFILE.
    """
    for profile in profiles:
        if result := _sync(profile):
            (completed_tasks, total_tasks) = result
            log.info(f"{profile} synced {completed_tasks}/{total_tasks} tasks")
