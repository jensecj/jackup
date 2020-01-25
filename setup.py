#!/usr/bin/env python

import os
import sys
from setuptools import setup, find_packages


py_version = sys.version_info[:2]
if py_version < (3, 8):
    print(f"jackup requires Python 3.8+ ({py_version} detected).")
    sys.exit(-1)


version = open("__version__.py", "r").read().strip()
setup(
    name="jackup",
    version=version,
    description="Simple synchronization",
    url="http://github.com/jensecj/jackup",
    author="Jens Christian Jensen",
    author_email="jensecj@gmail.com",
    packages=find_packages(),
    entry_points={"console_scripts": ["jackup = jackup.cli:main"],},
    zip_safe=False,
)
