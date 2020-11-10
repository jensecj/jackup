import os
import json
import logging

from typing import List
from types import SimpleNamespace as Namespace

from .config import CONFIG

log = logging.getLogger(__name__)


def path_to_profile(profile: str) -> str:
    """
    Returns the path to the file belonging to PROFILE.
    """
    if profile:
        return os.path.join(CONFIG.config_path, profile + ".json")


def exists(profile: str) -> bool:
    """
    Returns whether PROFILE exists.
    Is checked by the existence of the corresponding file in the jackup
    directory.
    """
    if path := path_to_profile(profile):
        return os.path.isfile(path)


def load(profile: str):
    """
    Reads the content of the profile-file from disk, and returns it as a Profile.
    """
    default_task = {
        "exclude": [],
        "args": [],
        "src_mounted": False,
        "dest_mounted": False,
    }

    profile_file = path_to_profile(profile)
    with open(profile_file, "r") as db:
        tasks = json.load(db, object_hook=lambda d: Namespace(**{**default_task, **d}))

    return tasks


def path_to_profile_lock(profile: str) -> str:
    """
    Returns the path to the lockfile belonging to PROFILE.
    """
    return os.path.join(CONFIG.config_path, profile + ".lock")


def profiles() -> List[str]:
    """
    Get the names of all available profiles on the system.
    This is done by finding all profile-files (files ending in .json) in the
    jackup directory.
    """
    # list all files in the jackup directory that end with '.json', these are the profiles
    return [
        # dont include the last 5 charaters of the filename ('.json')
        os.path.splitext(profile)[0]
        for profile in os.listdir(CONFIG.config_path)
        if profile.endswith(".json")
    ]


def tasks(profile: str):
    """
    Returns all tasks in a profile, sorted by order of synchronization
    """
    tasks = load(profile)
    return tasks


def lock(profile: str) -> bool:
    """
    Locks the specified PROFILE, so it can no longer be synchronized.
    Returns True if profile was locked successfully,
    returns False if the profile was already locked.
    """
    lockfile_path = path_to_profile_lock(profile)

    if os.path.isfile(lockfile_path):
        return False

    with open(lockfile_path, "w") as f:
        f.write(str(os.getpid()))

    return True


def unlock(profile: str) -> None:
    """
    Unlocks the specified PROFILE, so that it can again be synchronized.
    """
    lockfile = path_to_profile_lock(profile)
    if os.path.isfile(lockfile):
        os.remove(lockfile)
