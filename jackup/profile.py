import os
import json

def path_to_profile(config, profile):
    """
    Returns the path to the profile-file belonging to PROFILE.
    """
    return os.path.join(config['dir'], profile + '.json')

def exists(config, profile):
    """
    Returns whether PROFILE exists.
    Is checked by the existence of the corresponding file in the jackup
    directory.
    """
    path = path_to_profile(config, profile)
    return os.path.isfile(path)

def create(config, profile):
    """
    Creates a new empty jackup profile, with the given name.
    """
    path = path_to_profile(config, profile)
    with open(path, 'w') as profile_db:
        json.dump({}, profile_db, indent=4)

def read(config, profile):
    """
    Reads the content of the profile-file from disk, and returns it.
    """
    profile_file = path_to_profile(config, profile)
    with open(profile_file, 'r') as profile_db:
        tasks = json.load(profile_db)

    return tasks

def write(config, profile, content):
    """
    Writes new content to the profile-file on disk.
    """
    profile_file = path_to_profile(config, profile)
    with open(profile_file, 'w') as profile_db:
        json.dump(content, profile_db, indent=4)

def path_to_profile_lock(config, profile):
    """
    Returns the path to the lockfile belonging to PROFILE.
    """
    return os.path.join(config['dir'], profile + '.lock')

def profiles(config):
    """
    Get the names of all available profiles on the system.
    This is done by finding all profile-files (files ending in .json) in the
    jackup directory.
    """
    profiles = [ profile[:-5] # dont include the last 5 charaters of the filename ('.json')
                 for profile
                 in os.listdir(config['dir']) # list all files in the jackup directory
                 if profile.endswith('.json') ] # that end with '.json', these are the profiles
    return profiles

def _sort_task_ids_by_order(profile):
    """
    Returns a list of task ids from PROTILE, sorted by the order in which they will
    be synchronized.
    """
    return sorted(profile, key = lambda task: profile[task]['order'])

def tasks(config, profile_name):
    """
    Returns all tasks in a profile, sorted by order of synchronization
    """
    profile = read(config, profile_name)
    sorted_ids = _sort_task_ids_by_order(profile)

    return [ profile[id] for id in sorted_ids ]

def max_order(profile):
    """
    Get the highest order of any task in PROFILE
    """
    # if there are no tasks in the profile, the new ordering starts at 1.
    if len(profile) == 0:
        return 1

    orders = [ profile[task]['order'] for task in profile ]
    return max(orders)

def lock(config, profile):
    """
    Locks the specified PROFILE, so it can no longer be synchronized.
    Returns True if profile was locked successfully,
    returns False if the profile was already locked.
    """
    lockfile = path_to_profile_lock(config, profile)

    if os.path.isfile(lockfile):
        return False

    open(lockfile, 'w').close()
    return True

def unlock(config, profile):
    """
    Unlocks the specified PROFILE, so that it can again be synchronized.
    """
    lockfile = path_to_profile_lock(config, profile)
    if os.path.isfile(lockfile):
        os.remove(lockfile)
