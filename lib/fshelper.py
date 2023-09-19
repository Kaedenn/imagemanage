#!/usr/bin/env python

"""
Functions to simplify dealing with files, directories, and the like.
"""

import os

import lib.log
logger = lib.log.DeferredLogger(__name__)

@lib.log.traced_function(logger, when="both", trace_func="trace")
def _get_files_of(entry, depth, depth_max, soft_errors):
  "Recursively get the file(s) given by the single entry"
  if not os.path.exists(entry):
    logger.error("Entry %r does not exist", entry)
    if not soft_errors:
      raise FileNotFoundError(entry)
  elif os.path.isdir(entry):
    if depth_max == -1 or depth + 1 <= depth_max:
      for child_name in os.listdir(entry):
        child = os.path.join(entry, child_name)
        yield from _get_files_of(child, depth+1, depth_max, soft_errors)
    elif depth_max == 0:
      logger.info("Skipping directory %r", entry)
    else:
      logger.info("Skipping directory %r; max depth %d reached", entry, depth)
  else:
    if not os.path.isfile(entry):
      logger.warning("%r neither file not directory; adding anyway", entry)
    yield entry

@lib.log.traced_function(logger, when="both", trace_func="trace", pretty=True)
def get_files(entry_list, recurse_max=1, soft_errors=False):
  """
  Get the files specified by the list of paths

  recurse_max   maximum recursion depth: 0 to disable, -1 for infinite
  """
  results = []
  for entry in entry_list:
    results.extend(_get_files_of(entry, 0, recurse_max, soft_errors))
  return results

# vim: set ts=2 sts=2 sw=2:
