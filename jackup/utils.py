import os
import subprocess
from typing import Tuple


def print_table(rows):
    # figure out column widths
    widths = [len(max(columns, key=len)) for columns in zip(*rows)]

    # print header
    header, data = rows[0], rows[1:]
    headings = [format(title, f"{width}s") for width, title in zip(widths, header)]
    print(" | ".join(headings))

    # print header separator
    print("-+-".join("-" * width for width in widths))

    # print data
    for row in data:
        cols = [format(cdata, "%ds" % width) for width, cdata in zip(widths, row)]
        print(" | ".join(cols))


# TODO: Convert to pure python instead of relying on UNIX tools.


def ssh_can_connect(host: str, port: str) -> int:
    """
    Returns c-style error codes, whether we can connect to a host through ssh.
    0: No error
    """
    cmd_ssh = subprocess.run(["ssh", "-p", port, host, "exit 0"])
    return not cmd_ssh.returncode


def mountpoint_from_uuid(uuid: str) -> str:
    """
    Returns the path where a device with UUID is mounted.
    If the device is not mounted, then return the empty string.
    """
    cmd_findmnt = subprocess.run(
        ["findmnt", "-rn", "-S", "UUID=" + uuid, "-o", "TARGET"], stdout=subprocess.PIPE
    )
    return str(cmd_findmnt.stdout, "utf-8", "ignore").strip()


# uuids = ["28B88482B884506C", "027E2FC17E2FAC7B"]
# for uuid in uuids:
#     mnt_point = mountpoint_from_uuid(uuid)
#     if mnt_point:
#         print(uuid + " is mounted at " + mnt_point)
#     else:
#         print(uuid + " is not mounted")


def uuid_relpath_pair_from_path(path: str) -> Tuple[str, str]:
    """
    Generates a (UUID, relative path) pair from a path on the file system.
    This is done by figuring out which device the path belongs to, and then
    finding its mountpoint, the relative path is then calculated based on where
    the device is mounted.
    """
    cmd_df = subprocess.run(["df", "--output=source", path], stdout=subprocess.PIPE)
    device = str(cmd_df.stdout, "utf-8", "ignore")[10:].strip()

    cmd_lsblk = subprocess.run(
        ["lsblk", "-f", device, "-oUUID"], stdout=subprocess.PIPE
    )
    uuid = str(cmd_lsblk.stdout, "utf-8", "ignore")[4:].strip()

    cmd_mountpoint = subprocess.run(
        ["lsblk", "-f", device, "-oMOUNTPOINT"], stdout=subprocess.PIPE
    )
    mountpoint = str(cmd_mountpoint.stdout, "utf-8", "ignore")[10:].strip()

    uuid_relative_path = path
    if path.startswith(mountpoint):
        uuid_relative_path = path[len(mountpoint) :].strip("/")

    return (uuid, uuid_relative_path)


# paths = ["/mnt/extern/images", "/home/jens/test"]
# for p in paths:
#     print(uuid_relpath_pair_from_path(p))


def path_from_uuid_relpath(uuid: str, relpath: str) -> str:
    """
    Reifies a filesystem path from a (UUID, relative path) pair.
    This is done by finding the mountpoint of the device belonging to the UUID, then
    glueing the relative path onto mountpoint.
    """
    mnt_point = mountpoint_from_uuid(uuid)
    return os.path.join(mnt_point, relpath)


# uuid_paths = [["027E2FC17E2FAC7B", "images"],
#               ["d047f2a2-6a9b-4f9c-9c3b-bd3c418babe9", "home/jens/vault"]]
# for uu,pp in uuid_paths:
#     print(uu + " + " + pp + " = " + path_from_uuid_relpath(uu,pp))
