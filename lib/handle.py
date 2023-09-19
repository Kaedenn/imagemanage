#!/usr/bin/env python3

"""
Provide a simple "unique handle builder" class for building unique handles
(basically reference IDs) to objects.
"""

import lib.log
logger = lib.log.DeferredLogger(__name__)

class Handles:
  """
  Build globally-unique IDs
  """
  def __init__(self):
    "See help(type(self))"
    self._id = 0

  def next(self):
    "Advance to and return the next handle"
    self._id = self._id + 1
    return self._id

# vim: set ts=2 sts=2 sw=2:
