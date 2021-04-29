#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This file is used to create the package we'll publish to PyPI.

.. currentmodule:: setup.py
.. moduleauthor:: Nathan Derave <deravenathan@hotmail.com>
"""

import importlib.util
import os
from pathlib import Path
from setuptools import setup, find_packages
from pkg_resources import parse_requirements
from codecs import open  # Use a consistent encoding.
from os import path

here = path.abspath(path.dirname(__file__))

# Get the base version from the library.  (We'll find it in the `version.py`
# file in the src directory, but we'll bypass actually loading up the library.)
vspec = importlib.util.spec_from_file_location(
    "version", str(Path(__file__).resolve().parent / "jaskier" / "version.py")
)
vmod = importlib.util.module_from_spec(vspec)
vspec.loader.exec_module(vmod)
version = getattr(vmod, "__version__")

# Parse requirements
with open("requirements.txt") as f:
    install_requires = []
    for req in parse_requirements(f.read()):
        install_requires.append(str(req).replace("==", ">="))

# If the environment has a build number set...
if os.getenv("buildnum") is not None:
    # ...append it to the version.
    version = "{version}.{buildnum}".format(
        version=version, buildnum=os.getenv("buildnum")
    )

setup(
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    version=version,
    include_package_data=True,
    install_requires=install_requires,
)
