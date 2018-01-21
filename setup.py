from setuptools import setup

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
