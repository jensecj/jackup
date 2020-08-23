import os
import json

from typing import List
from types import SimpleNamespace as Namespace
from dataclasses import dataclass

import jackup.logging as log

from jackup.config import Config
from jackup.task import Task


@dataclass(frozen=True)
class Profile:
    name: str
    tasks: List[Task]


def path_to_profile(config: Config, profile_name: str) -> str:
    """
    Returns the path to the file belonging to PROFILE.
    """
    if profile_name:
        return os.path.join(config.jackup_path, profile_name + ".json")


def exists(config: Config, profile_name: str) -> bool:
    """
    Returns whether PROFILE exists.
    Is checked by the existence of the corresponding file in the jackup
    directory.
    """
    if path := path_to_profile(config, profile_name):
        return os.path.isfile(path)


def read(config: Config, profile_name: str):
    """
    Reads the content of the profile-file from disk, and returns it as a Profile.
    """
    default = {"exclude": [], "args": []}

    profile_file = path_to_profile(config, profile_name)
    with open(profile_file, "r") as db:
        tasks = json.load(db, object_hook=lambda d: Namespace(**{**default, **d}))

    return tasks


def path_to_profile_lock(config: Config, profile_name: str) -> str:
    """
    Returns the path to the lockfile belonging to PROFILE.
    """
    return os.path.join(config.jackup_path, profile_name + ".lock")


def profiles(config: Config) -> List[str]:
    """
    Get the names of all available profiles on the system.
    This is done by finding all profile-files (files ending in .json) in the
    jackup directory.
    """
    # list all files in the jackup directory that end with '.json', these are the profiles
    return [
        # dont include the last 5 charaters of the filename ('.json')
        os.path.splitext(profile)[0]
        for profile in os.listdir(config.jackup_path)
        if profile.endswith(".json")
    ]


def tasks(config: Config, profile_name: str) -> List[Task]:
    """
    Returns all tasks in a profile, sorted by order of synchronization
    """
    tasks = read(config, profile_name)
    return tasks


def lock(config: Config, profile_name: str) -> bool:
    """
    Locks the specified PROFILE, so it can no longer be synchronized.
    Returns True if profile was locked successfully,
    returns False if the profile was already locked.
    """
    lockfile_path = path_to_profile_lock(config, profile_name)

    if os.path.isfile(lockfile_path):
        return False

    open(lockfile_path, "w").close()
    return True


def unlock(config: Config, profile_name: str) -> None:
    """
    Unlocks the specified PROFILE, so that it can again be synchronized.
    """
    lockfile_path = path_to_profile_lock(config, profile_name)
    if os.path.isfile(lockfile_path):
        os.remove(lockfile_path)
