import os
import json

from typing import List
from types import SimpleNamespace as Namespace

import jackup.log as log


def path_to_profile(config, profile: str) -> str:
    """
    Returns the path to the file belonging to PROFILE.
    """
    if profile:
        return os.path.join(config.config_path, profile + ".json")


def exists(config, profile: str) -> bool:
    """
    Returns whether PROFILE exists.
    Is checked by the existence of the corresponding file in the jackup
    directory.
    """
    if path := path_to_profile(config, profile):
        return os.path.isfile(path)


def load(config, profile: str):
    """
    Reads the content of the profile-file from disk, and returns it as a Profile.
    """
    default = {"exclude": [], "args": []}

    profile_file = path_to_profile(config, profile)
    with open(profile_file, "r") as db:
        tasks = json.load(db, object_hook=lambda d: Namespace(**{**default, **d}))

    return tasks


def path_to_profile_lock(config, profile: str) -> str:
    """
    Returns the path to the lockfile belonging to PROFILE.
    """
    return os.path.join(config.config_path, profile + ".lock")


def profiles(config) -> List[str]:
    """
    Get the names of all available profiles on the system.
    This is done by finding all profile-files (files ending in .json) in the
    jackup directory.
    """
    # list all files in the jackup directory that end with '.json', these are the profiles
    return [
        # dont include the last 5 charaters of the filename ('.json')
        os.path.splitext(profile)[0]
        for profile in os.listdir(config.config_path)
        if profile.endswith(".json")
    ]


def tasks(config, profile: str):
    """
    Returns all tasks in a profile, sorted by order of synchronization
    """
    tasks = load(config, profile)
    return tasks


def lock(config, profile: str) -> bool:
    """
    Locks the specified PROFILE, so it can no longer be synchronized.
    Returns True if profile was locked successfully,
    returns False if the profile was already locked.
    """
    lockfile_path = path_to_profile_lock(config, profile)

    if os.path.isfile(lockfile_path):
        return False

    with open(lockfile_path, "w") as f:
        f.write(str(os.getpid()))

    return True


def unlock(config, profile: str) -> None:
    """
    Unlocks the specified PROFILE, so that it can again be synchronized.
    """
    lockfile = path_to_profile_lock(config, profile)
    if os.path.isfile(lockfile):
        os.remove(lockfile)
