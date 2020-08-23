import os
import pkg_resources

from types import SimpleNamespace as Namespace


SEMVER = pkg_resources.require("jackup")[0].version

config_path = os.path.expanduser("~/.config/jackup/")
log_path = os.path.join(config_path, "jackup.log")  # TODO: log to /var/log?

CONFIG = Namespace(**{"config_path": config_path, "log_path": log_path})
