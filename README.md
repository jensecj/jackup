# What is Jackup?
Jackup is a simple file duplicator.

I have a server in my living room, and I also have
an external harddrive I bring with me.

Jackup allows me to do funny things like:
```bash
# go to path I want to duplicate
cd /home/jens/vault
# initialize new repo here
jackup init

# add a folder on my external harddrive as a slave for this folder
jackup add exhdd /mnt/extern/backups/

# now i unplug my external harddrive from my laptop, and connect it to the server in my living room

# add the same folder as a slave, this time while it is connected to the server
# this also works for machines that are more than 20ft away
jackup add --ssh --port 2222 lrserv stuetop@192.168.0.40:/media/extern/backups/
```

Now, whenever I run `jackup sync` from my vault folder, Jackup will try to push
changes to the slaves, and it will work if my external harddrive is connected to
either my laptop or my server. I usually have it running as a cronjob.

Behind the scenes, Jackup uses rsync to push changes from the master folder to
the slaves, so transfers are incremental and compressed.

# Notes
The goal was to be easy and fast to setup, and "just work", however, this is
pre-alpha software, use with causion, it may spirit-away your files.

# Usage
For help see `jackup --help`, or command specific help with `jackup <command> --help`.

To start off with you need to initialize a new repository, this is done in the
directory you want to duplicate to the slaves.
```bash
$ jackup init
```

Adding a slave to the repository:
```bash
$ jackup add [--ssh] [--port N] <name> <path>
```
the name is the qualifier you're going to use to refer to the slave in the
future.

The path can either be local to the machine Jackup is running on, or an SSH-path
to a directory you have access to on a remote machine.

In either case, the path will be analyzed and split into a `(device-UUID,
relative-path)` pair, which is used to locate the path when we need to sync, this
allows you to easily sync to removable storage, even if they are remounted under
different names later.

Removing a slave from the repository is done by name:
```bash
$ jackup remove <name>
```

Once you're ready to sync, just run:
```bash
$ jackup sync
```
Jackup will then try to sync to all available slaves, if a slave is unavailable
(no SSH-connection, unmounted, etc.) Jackup will tell you.

You can also list all slaves currently in the repository:
```bash
$ jackup list
```
which gives you a list like this:

```
MASTER: /home/jens/vault/projects/python/jackup will duplicate to:
name        | type  | path                       | uuid/relpath / host/port
------------+-------+----------------------------+--------------------------
exhdd       | local | /mnt/extern/backups        | 027E2FC17E2FAC7B/test
lrserv      | ssh   | /home/stuetop/JENS/backups | stuetop@192.168.0.40/2222
```

# Installation

There is no way to install Jackup yet, one way to use it is to clone the repo,
symlink `jackup.py` to `/usr/bin/jackup`, and install the prerequisites:

(these are not strict requirements, they're just the only ones I've tested)
* Python >= 3.6
* rsync >= 3.1.2
* linux sys utilities (`lsblk` / `fndmnt` / `df`)
