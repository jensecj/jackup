import os
import json

from typing import List
from dataclasses import dataclass

import jackup.logging as log
import jackup.task as T

from jackup.config import Config
from jackup.task import Task

@dataclass
class Profile:
    name: str
    tasks: List[Task]

def toJSON(profile: Profile):
    return [ T.toJSON(task) for task in profile.tasks ]

def fromJSON(tasks) -> List[Task]:
    return [ T.fromJSON(task) for task in tasks ]

def add(profile: Profile, task: Task) -> Profile:
    "Adds a TASK to a PROFILE."
    new_tasks = profile.tasks
    new_tasks.append(task)
    new_profile = Profile(profile.name, new_tasks)
    return new_profile

def get_profile_by_name(config: Config, profile_name: str) -> Profile:
    """
    If a profile with PROFILE_NAME exists, it is returned, otherwise it is
    created.
    """
    if not exists(config, profile_name):
        log.info('Profile does not exist, creating...')
        create(config, profile_name)

    tasks = read(config, profile_name)

    return Profile(profile_name, tasks)

def path_to_profile(config: Config, profile_name: str) -> str:
    """
    Returns the path to the file belonging to PROFILE.
    """
    return os.path.join(config.jackup_path, profile_name + '.json')

def exists(config: Config, profile_name: str) -> bool:
    """
    Returns whether PROFILE exists.
    Is checked by the existence of the corresponding file in the jackup
    directory.
    """
    path = path_to_profile(config, profile_name)
    return os.path.isfile(path)

def create(config: Config, profile_name: str) -> None:
    """
    Creates a new empty PROFILE, with the given name.
    """
    path = path_to_profile(config, profile_name)
    with open(path, 'w') as profile_db:
        json.dump({}, profile_db, indent=4)

def read(config: Config, profile_name: str):
    """
    Reads the content of the profile-file from disk, and returns it.
    """
    profile_file = path_to_profile(config, profile_name)
    with open(profile_file, 'r') as profile_db:
        tasks = json.load(profile_db)

    return fromJSON(tasks)

def write(config: Config, profile_name: str, content) -> None:
    """
    Writes new content to the profile-file on disk.
    """
    profile_file = path_to_profile(config, profile_name)
    with open(profile_file, 'w') as profile_db:
        json.dump(content, profile_db, indent=4)

def path_to_profile_lock(config: Config, profile_name: str) -> str:
    """
    Returns the path to the lockfile belonging to PROFILE.
    """
    return os.path.join(config.jackup_path, profile_name + '.lock')

def profiles(config: Config) -> List[str]:
    """
    Get the names of all available profiles on the system.
    This is done by finding all profile-files (files ending in .json) in the
    jackup directory.
    """
    profiles = [ profile[:-5] # dont include the last 5 charaters of the filename ('.json')
                 for profile
                 in os.listdir(config.jackup_path) # list all files in the jackup directory
                 if profile.endswith('.json') ] # that end with '.json', these are the profiles
    return profiles

def tasks(config: Config, profile_name: str):
    """
    Returns all tasks in a profile, sorted by order of synchronization
    """
    tasks = read(config, profile_name)
    return sorted(tasks, key = lambda task: task.order)

def orders(tasks) -> List[int]:
    """
    Returns a list of all orders in use in PROFILE
    """
    return [ task.order for task in tasks ]

def max_order(tasks) -> int:
    """
    Get the highest order of any task in TASKS
    """
    # if there are no tasks in the tasks, the new ordering starts at 1.
    if len(tasks) == 0:
        return 1

    return max(orders(tasks))

def lock(config: Config, profile_name: str) -> bool:
    """
    Locks the specified PROFILE, so it can no longer be synchronized.
    Returns True if profile was locked successfully,
    returns False if the profile was already locked.
    """
    lockfile_path = path_to_profile_lock(config, profile_name)

    if os.path.isfile(lockfile_path):
            return False

    open(lockfile_path, 'w').close()
    return True

def unlock(config: Config, profile_name: str) -> None:
    """
    Unlocks the specified PROFILE, so that it can again be synchronized.
    """
    lockfile_path = path_to_profile_lock(config, profile_name)
    if os.path.isfile(lockfile_path):
        os.remove(lockfile_path)
