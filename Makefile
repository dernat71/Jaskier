.DEFAULT_GOAL := install
.PHONY: test lint
PROJ_SLUG = jaskier
CLI_NAME = jaskier
PY_VERSION = 3.8
LINTER = flake8

install:
	pip install -e . 

dev:
	pip install -e  '.[dev]' 

black:
	black .

lint: black
	$(LINTER) $(PROJ_SLUG)

test: lint
	py.test --cov-report term --cov=$(PROJ_SLUG) tests/
