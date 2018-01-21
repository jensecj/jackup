import sys
from setuptools import setup

version = sys.version_info[:2]
if version < (3, 6):
    print('jackup requires Python version 3.6 or later' + ' ({}.{} detected).'.format(*version))
    sys.exit(-1)

setup(name='jackup',
      version='0.1',
      description='Simple synchronization',
      url='http://github.com/jensecj/jackup',
      author='Jens Christian Jensen',
      author_email='jensecj@gmail.com',
      packages=['jackup'],
      entry_points = {
          'console_scripts': ['jackup=jackup.cli:main'],
      },
      zip_safe=False)
