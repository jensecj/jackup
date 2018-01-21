[![Build Status](https://travis-ci.org/jensecj/jackup.svg?branch=master)](https://travis-ci.org/jensecj/jackup)

# What is Jackup?
Jackup is a simple file synchronizer.

I have a server in my living room, and I also have
an external harddrive I bring with me.

Jackup allows me to do funny things like:
```bash
# go to path I want to duplicate
cd /home/jens/vault
# initialize new repo here
jackup init

# add a folder on my external harddrive as a slave for this folder
jackup add exhdd --push /mnt/extern/backups/

# now i unplug my external harddrive from my laptop, and connect it to the server in my living room

# add the same folder as a slave, this time while it is connected to the server
# this also works for machines that are more than 20ft away
jackup add lrserv --push --ssh --port 2222 stuetop@192.168.0.40:/media/extern/backups/
```

Now, whenever I run `jackup sync` from my vault folder, Jackup will try to push
changes to the slaves, and it will work if my external harddrive is connected to
either my laptop or my server. I usually have it running as a cronjob.

My server also has a couple of disks, they're different kinds, sizes, etc. so
running them in raid would be a bother.
I have Jackup setup so it has a master directory on my laptop, which I use for
all sorts of things I would like to save, from there it pulls pictures and
videos from my phone, which is running an ssh-daemon.
It then pushes the master directory to an external harddrive, usually connected
to my laptop, and also pushes the folder to a disk on my server, and from there
the server uses Jackup to mirror one disk onto the other one.

I set it up on the laptop part like this:
```bash
# go to the master directory and init a new repository
cd /home/jens/master
jackup init

# I want to pull the media folder from my phone into the master dir
jackup add phone_imgs --pull --ssh --port 8022 jens@192.168.0.4:/home/storage/media

# and I want to push to the external harddrive and my server
jackup add local_bu --push /mnt/extern/backups
jackup add serv_bu --push --ssh --port 22 stuetop@192.168.0.40:/home/stuetop/JENS/backups
```

And then i just have `(cd /home/jens/master; jackup sync)` running in a cropjob.

Behind the scenes, Jackup uses rsync to synchronize the master folder and
the slaves, so transfers are incremental and compressed.

# Notes
The goal was to be easy to use, fast to setup, and "just work", however, this is
pre-alpha software, use with causion, it may spirit-away your files.

# Usage
For help see `jackup --help`, or command specific help with `jackup <command> --help`.

To start off with you need to initialize a new repository, this is done in the
directory you want to synchronize with the slaves.
```bash
$ jackup init
```

Adding a slave to the repository:
```bash
$ jackup add <name> [--ssh] [--port N] [--push / --pull] <path>
```
the name is the qualifier you're going to use to refer to the slave in the
future.

The path can either be local to the machine Jackup is running on, or an SSH-path
to a directory you have access to on a remote machine.

`--push / --pull` indicates whether the master will push its content to the
slave, or pull the content from the slave down to the master directory.

The path will be analyzed and split into a `(device-UUID, relative-path)` pair,
which is used to locate the path when we need to sync, this allows you to easily
sync to removable storage, even if they are remounted under different names
later.

Removing a slave from the repository is done by name:
```bash
$ jackup remove <name>
```

Once you're ready to sync, run:
```bash
$ jackup sync
```
Jackup will then try to sync to all available slaves, it will try pulling changes before pushing.
If a slave is unavailable (no SSH-connection, unmounted, etc.) Jackup will tell you.

You can also list all slaves in the repository:
```bash
$ jackup list
```

which gives you a list like this:
```
MASTER: /home/jens/master will duplicate to:
name       | action | type  | path                       | uuid/relpath / host/port
-----------+--------+-------+----------------------------+------------------------------
phone_imgs | pull   | ssh   | /home/storage/media        | jens@192.168.0.4/8022
local_bu   | push   | local | /mnt/extern/backups        | 027E2FC17E2FAC7B/jens/backups
serv_bu    | push   | ssh   | /home/stuetop/JENS/backups | stuetop@192.168.0.40/22
```

# Installation

Clone the repo and run `pip install . && pip install -r requirements.txt`.

Remember to install the prerequisites:

(these are not strict requirements, they're just the only ones I've tested)
* Python >= 3.6
* rsync >= 3.1.2
* linux sys utilities (`lsblk` / `fndmnt` / `df`)
