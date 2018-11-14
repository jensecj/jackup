.PHONY: default
default: check test

check:
	mypy jackup

test:
	pytest

install:
	pip install -e .

clean:
	rm -r dist build jackup.egg-info __pycache__

deps:
	pip install -r requirements.txt

freeze:
	pip freeze > requirements.txt

env:
	source env/bin/activate
