#!/usr/bin/env python

"""
Global constants available as a self-contained module.
"""

ASSET_PATH = "assets"
FONT = "monospace"
FONT_SIZE = 10

SORT_NONE = "none" # unordered
SORT_RAND = "rand" # randomized
SORT_NAME = "name" # ascending
SORT_TIME = "time" # oldest first
SORT_SIZE = "size" # smallest first
SORT_RNAME = "r" + SORT_NAME # descending
SORT_RTIME = "r" + SORT_TIME # newest first
SORT_RSIZE = "r" + SORT_SIZE # largest first
SORT_MODES = (
  SORT_NONE, SORT_RAND,
  SORT_NAME, SORT_RNAME,
  SORT_TIME, SORT_RTIME,
  SORT_SIZE, SORT_RSIZE)

SCALE_NONE = "none"
SCALE_SHRINK = "shrink"
SCALE_EXACT = "exact"

MODE_NONE = "none"
MODE_RENAME = "rename"
MODE_GOTO = "goto"
MODE_SET_IMAGE = "set-image"
MODE_LABEL = "label"
MODE_COMMAND = "command"

LINE_FORMAT = "{} {}\n"

INPUT_START_WIDTH = 20

PADDING = 2

# vim: set ts=2 sts=2 sw=2:
