#!/usr/bin/env python3

"""
Top-level configuration for the imagemanage.py test suite
"""

import pytest
import os
import shutil
import sys

pytest_plugins = ["pytester"]

# To allow tests to import the modules being tested
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))

def pytest_addoption(parser):
  parser.addoption("--workdir", help="temporary working directory")
  # parser.addoption("--option2", action="store_true", help="...")

def pytest_configure(config):
  workdir = config.getoption("--workdir")
  if workdir is not None:
    if not os.path.exists(workdir):
      sys.stderr.write(f"tests: creating directory {workdir!r}\n")
      shutil.makedirs(workdir)

@pytest.fixture(scope="session")
def assets_config(pytestconfig, tmp_path_factory):
  "Provide all the configuration needed for interacting with testing assets"
  assets_local = tmp_path_factory.mktemp("test-assets")
  return {
    "icons-path": pytestconfig.getoption("--icons-path"),
    "assets-local": assets_local,
    "icons-local": os.path.join(assets_local, "icons")
  }

@pytest.fixture(scope="session")
def local_icons(pytestconfig, assets_config):
  ipath = assets_config["icons-path"]
  ilocal = assets_config["icons-local"]
  debug_write(f"Copying {ipath} to {ilocal}...")
  shutil.copytree(ipath, ilocal)
  return ilocal

# vim: set ts=2 sts=2 sw=2:

