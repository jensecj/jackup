[![Build Status](https://travis-ci.org/jensecj/jackup.svg?branch=master)](https://travis-ci.org/jensecj/jackup)

# What is Jackup?
Jackup is a simple file synchronizer.

I have a server in my living room, and I also have
an external harddrive I bring with me.

Jackup allows me to do funny things like:
```bash
# push my vault folder to backups on my external harddrive
jackup add backup_vault exhdd /home/jens/vault /mnt/extern/backups/

# now i unplug my external harddrive from my laptop, and connect it to the server in my living room

# add the same folder as a slave, this time while it is connected to the server
# this also works for machines that are more than 20ft away
jackup add backup_vault server /home/jens/vault stuetop@192.168.0.40:/media/extern/backups/
```

Now, whenever I run `jackup sync backup_vault`, Jackup will try to push
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
# I want to pull the media folder from my phone into the master dir
jackup add backup grab_phone_media jens@192.168.0.4:/home/storage/media /home/jens/master/phone

# and I want to push to the external harddrive and my server
jackup add backup to_exhdd /home/jens/master /mnt/extern/backups
jackup add backup to_server /home/jens/master stuetop@192.168.0.40:/home/stuetop/JENS/backups
```

And then i just have `jackup sync backup` running in a cronjob.

Behind the scenes, Jackup uses rsync to synchronize the folders, so transfers
are incremental and compressed.

# Notes
The goal was to be easy to use, fast to setup, and "just work", however, this is
pre-alpha software, use with causion, it may spirit-away your files.

# Usage
For help see `jackup --help`, or command specific help with `jackup <command> --help`.

To start off with you need to create a profile, and add some actions to it.
A new profile is automatically created as you start adding:
```bash
$ jackup add <profile> <name> <source> <destination> [--priority N]
```
The profile name is what you refer to when you want to sync.

the name is the qualifier you're going to use to refer to the slave in the
future, if you want to edit or remove it.

The paths can either be local to the machine or SSH-paths to directories you
have access to on remote machines.

`--priority` takes a number, and indicates in which order the slaves will be
synched, 0 being the first one.

Removing a slave from the profile is done by name:
```bash
$ jackup remove <profile> <name>
```

If you want to change something in a slave you have already added to a profile,
you can use `edit`:
```bash
$ jackup edit <profile> <name> [--source <path>] [--destination <path>] [--priority <number>]
```
Where each flag changes the related property of the slave. Multiple flags can be
used at the same time.

Once you're ready to sync, run:
```bash
$ jackup sync <profile>
```
Jackup will then try to sync to all available slaves, it will perform
synchronization in the order determined by each slaves priority, from smallest
to largest (smallest will be synchronized first).
If a slave is unavailable (no SSH-connection, unmounted, etc.) Jackup will tell
you.

You can also list all slaves in the profile:
```bash
$ jackup list [<profile>]
```

If run without a profile, it will list all available profiles on the system,
otherwise it lists all slaves in the profile given.

which gives you a list like this:
```
name             | source                               | destination                          | priority
-----------------+--------------------------------------+--------------------------------------+---------
grab_phone_media | jens@192.168.0.4:/home/storage/media | /home/jens/master                    | 0
to_exhdd         | /home/jens/master                    | /mnt/extern/backups                  | 1
to_server        | /home/jens/master                    | jens@192.168.0.4:/home/stuetop/JENS/ | 2

```

# Installation

Clone the repo and run `pip install . && pip install -r requirements.txt`.

Remember to install the prerequisites:

(these are not strict requirements, they're just the only ones I've tested)
* Python >= 3.6
* rsync >= 3.1.2
