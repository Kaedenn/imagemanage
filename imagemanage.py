#!/usr/bin/env python3
# pylint: disable=wildcard-import,unused-wildcard-import,too-many-function-args

"""
Display and manage a bunch of images.

This script essentially provides utilities for the following actions:
  Labelling an image
  "Marking" an image (for arbitrary actions, for tracking, etc)
  Moving (renaming) an image file
  Deleting an image

Note that this script does not modify the image files in any way; it neither
renames nor deletes files. Instead, the actions are printed with this script
terminates so that the user can decide how to proceed.

A user can certainly create a mark action to do such a thing, however.
"""

# https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QLabel.html
# https://doc.qt.io/qtforpython-6/PySide6/QtGui/QImage.html
# https://doc.qt.io/qtforpython-6/PySide6/QtGui/QPixmap.html
# https://doc.qt.io/qtforpython-6/PySide6/QtGui/QImageReader.html
# https://doc.qt.io/qtforpython-6/PySide6/QtGui/QBitmap.html
# https://doc.qt.io/qtforpython-6/PySide6/QtGui/QMovie.html
# Perhaps use stylesheets to configure text overlay?
# Perhaps use some sort of rich text or HTML for text overlay?

import argparse
import collections
import datetime
import functools
import logging
import mimetypes
import os
import shlex
import subprocess
from subprocess import Popen, PIPE
import sys

# pylint: disable=import-error, unused-import
from PySide6.QtCore import QPoint, Qt, Slot
from PySide6.QtWidgets import (
  QApplication,
  QFrame,
  QGridLayout,
  QLayout,
  QLabel,
  QLineEdit,
  QMainWindow,
  QPushButton,
  QStackedWidget,
  QVBoxLayout,
  QWidget)
from PySide6.QtGui import (
  QAction,
  QColor,
  QFont,
  QIcon,
  QImage,
  QMovie,
  QPainter,
  QPixmap)

from PySide6.QtMultimedia import QMediaPlayer, QVideoSink

# pylint: enable=import-error, unused-import

from lib import strtab
from lib import qhelper
from lib import valuehelper
from lib.constants import *
from lib.fshelper import get_files
import lib.handle
from lib.valuehelper import iter_none
import lib.log
lib.log.hotpatch(logging)

logging.basicConfig(format=lib.log.LOG_FORMAT, level=logging.INFO)
logger = lib.log.DeferredLogger(__name__)
logger.setFormat(lib.log.LOG_FORMAT)

# Default advance count for bulk advancing
ADVANCE_MANY_AMOUNT = 10

# Process execution helpers {{{0

def pipe_program(command, lines, stderr=sys.stderr):
  """
  Execute a command with the given input and return a list of output lines.

  The `command` argument must be either a string or a list of arguments.
  """
  inputs = [lines] if isinstance(lines, str) else lines
  args = shlex.split(command) if isinstance(command, str) else command
  logger.debug("exec %r with %d lines of input", command, len(lines))
  logger.trace("exec %r with %r", command, lines)
  input_text = os.linesep.join(inputs).encode()
  output = subprocess.check_output(args, input_text, stderr=stderr)
  output_lines = output.decode().splitlines()
  logger.debug("%r generated %d bytes (%d lines) of output", command,
      len(output), len(output_lines))
  return output_lines

# 0}}}

# Formatting helpers {{{0

# pylint: disable=redefined-builtin
def format_size(num_bytes, places=2, base=2, format="{num} {suffix}"):
  """
  Format a number of bytes as the best '<number> <scale>' string, rounded.

  `places` must be either None, zero, or a positive integer. Use None to
  disable rounding altogether.
  `base` must be either 2 or 10.
  `format` must be a str.format string containing both "{num}" and "{suffix}".
  """
  assert base in (2, 10), f"invalid base {base}; must be 2 or 10"
  prefixes = ["", "K", "M", "G", "T", "P"]
  scale, suffix = 1024.0, "B"
  if base == 10:
    scale = 1000.0
    if num_bytes >= scale:
      suffix = "iB" # never return "<num> iB"

  exponent = 0
  value = float(num_bytes)
  while value >= scale and exponent+1 < len(prefixes):
    value /= scale
    exponent += 1
  if places is not None:
    value = round(value, places)
  if places == 0:
    value = int(value)
  unit = f"{prefixes[exponent]}{suffix}"
  return format.format(num=value, suffix=unit)
# pylint: enable=redefined-builtin

def format_timestamp(tstamp, formatspec):
  "Format a numeric timestamp"
  return datetime.datetime.fromtimestamp(tstamp).strftime(formatspec)

# 0}}}

def iterate_from(sequence, start_index):
  """
  Iterate over a complete sequence starting at an arbitrary index.

  Starting index must be within the interval [-len(sequence), len(sequence)-1]
  """
  length = len(sequence)
  if start_index < 0:
    start_index += length
  curr = start_index
  assert 0 <= curr < length, f"{curr} outside the half interval [0, {length})"
  while curr < length:
    yield sequence[curr]
    curr += 1
  curr = 0
  while curr < start_index:
    yield sequence[curr]
    curr += 1

def get_icon(value):
  "Get a QIcon instance referring to the named icon"
  if os.path.exists(value):
    return QIcon(value)
  return QIcon.fromTheme(value)

def parse_color(color):
  "Parse a color value as a QColor"
  if isinstance(color, str):
    return QColor.fromString(color)
  if isinstance(color, int):
    return QColor.fromRgb(color)
  if isinstance(color, Qt.GlobalColor):
    return QColor(color)
  if isinstance(color, (list, tuple)):
    if len(color) in (3, 4):
      return QColor.fromRgb(*color)
  raise ValueError("Failed to parse color {!r}".format(color))

def parse_font(value, relative_to=None):
  "Parse a value as a QFont, optionally using an existing font as reference"
  if isinstance(value, QFont):
    return value

  if relative_to is not None:
    if not isinstance(relative_to, QFont):
      raise ValueError(f"relative_to must be a QFont, got {relative_to!r}")
    rel_font = relative_to
  else:
    rel_font = QFont(FONT, FONT_SIZE)

  font = QFont.fromString(rel_font.toString())
  if isinstance(value, dict):
    if "family" in value:
      font.setFamily(value["family"])
    if "size" in value:
      font.sizePointSize(value["size"])
    if "bold" in value:
      font.setBold(value["bold"])
    if "italic" in value:
      font.setItalic(value["italic"])
    if "underline" in value:
      font.setUnderline(value["underline"])
    if "weight" in value:
      font.setWeight(value["weight"])
  elif isinstance(value, str):
    font.setFamily(value)
  elif isinstance(value, tuple) and len(value) == 2:
    font.setFamily(value[0])
    font.setPointSize(value[1])
  elif isinstance(value, int):
    font.setPointSize(value)
  else:
    raise ValueError("Failed to parse font {!r}".format(value))
  return font

def _blocked_by_input(func):
  "Decorator that inhibits calling `func` if the input has focus"
  @functools.wraps(func)
  def wrapper(self, *args, **kwargs):
    "Wrapper function"
    if self.textbox.hasFocus():
      logger.debug("Input has focus; blocking %r call", lib.log.func_name(func))
      return None
    logger.trace("%s(*%s, **%s)", lib.log.func_name(func), args, kwargs)
    return func(self, *args, **kwargs)
  return wrapper

# TODO: Image scaling
# TODO: Image panning
# TODO: Enable/disable text drawing
class ImageDrawWidget(QWidget):
  """
  The primary widget for drawing images, videos, and possible overlay text

  This widget is effectively just a QPainter with additional sources.
  """
  def __init__(self, parent):
    "See help(type(self))"
    super().__init__(parent)
    self._handle_provider = lib.handle.Handles()
    self._text_objects = {}

    self._canvas = QLabel(self)

    # Rules by which to draw text
    self._color = QColor(Qt.GlobalColor.white)
    self._outline_color = QColor(Qt.GlobalColor.black)
    self._outline = True
    self._font = QFont(FONT, FONT_SIZE)
    self._align = Qt.AlignLeft
    # TODO: Anchor, scale mode, scale

    self._player = QMediaPlayer()
    self._video_provider = QVideoSink()
    self._video_provider.videoFrameChanged.connect(self._on_frame_changed)
    self._player.setVideoSink(self._video_provider)

  @property
  def canvas(self):
    return self._canvas

  @lib.log.traced_function(logger, when="both", trace_func="trace")
  def _on_frame_changed(self, frame):
    "The video sink is giving us a new frame to draw"
    self._current_frame = frame
    self.redraw()

  def redraw(self):
    "Trigger a redraw"
    frame_image = self._current_frame.toImage()
    with QPainter(self) as painter:
      pass

  def load(self, filename, play=True):
    "Load the given image or video"
    self._player.setSource(filename)
    if play:
      self._player.play()

  def set_text_attributes(self, **attrs): # TODO: Document what's available
    "Change how text is drawn; only applies to subsequent text"
    if "color" in attrs:
      self._color = parse_color(attrs["color"])
    if "outline_color" in attrs:
      self._outline_color = parse_color(attrs["outline_color"])
    if "outline" in attrs:
      self._outline = attrs["outline"]
    if "align" in attrs:
      self._align = attrs["align"]
    self._font = parse_font(attrs, relative_to=self._font)

  def get_text_handles(self):
    "Return all of the text handles currently being drawn"
    return tuple(self._text_object.keys())

  def is_text(self, handle):
    "True if the given handle is still being drawn"
    return handle in self._text_objects

  def get_text(self, handle):
    "Return the data for a specific text handle"
    if self.is_text(handle):
      return self._text_objects[handle]
    logger.warning("get_text() failed; %r is not a valid handle", handle)
    return None

  def add_text(self, pos, text, **attrs):
    """
    Draw text at the given position; returns a unique handle to the text to
    allow for later alteration or removal, if desired.
    """
    handle = self._handle_provider.next()

    # Aggregate all of the current settings


    # TODO: Trigger redraw
    return handle

  def clear_text(self, handles=()):
    "Clear the given text handles (or all text)"
    to_remove = handles
    if not handles:
      to_remove = self._text_objects.keys()
    for key in to_remove:
      if key not in self._text_objects:
        logger.warning("Text object %r does not exist; ignoring", key)
        continue
      data = self._text_objects[key]
      del self._text_objects[key]
    self.redraw()

class MainWidget(QWidget):
  """
  The main window primary widget
  """
  def __init__(self, parent):
    "Constructor; see help(type(self)) for usage"
    super().__init__(parent)
    self._path = None
    self._parent = parent

    self._layout = QVBoxLayout(self)
    self._layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
    self._input = QLineEdit()
    self._layout.addWidget(self._input)
    self._canvas = QLabel()
    self._widget = ImageDrawWidget(self._canvas)
    #self._canvas = QLabel("Test")
    #self._canvas.setAlignment(Qt.AlignCenter)
    #self._canvas.setObjectName("canvas")
    #self._canvas.setStyleSheet("* { width: 100%; height: 100%; top: 0; left: 0; }")
    self._layout.addWidget(self._widget)
    self.setLayout(self._layout)
    self.show()

  path = property(lambda self: self._path)
  layout = property(lambda self: self._layout)
  textbox = property(lambda self: self._input)
  canvas = property(lambda self: self._widget.canvas)

class ImageManager(QMainWindow):
  """
  The main image manager window
  """
  def __init__(self, images,
      width=None, height=None,
      show_text=False,
      font_family=FONT,
      font_size=FONT_SIZE,
      input_width=INPUT_START_WIDTH,
      icon=None,
      advance_many=ADVANCE_MANY_AMOUNT,
      **kwargs):
    "Constructor; see help(type(self)) for usage"
    super().__init__() # must be called explicitly (TODO: pass kwargs?)

    self.setWindowTitle("Image Manager") # Will be overridden shortly
    if icon is not None:
      self.setWindowIcon(get_icon(icon))

    self._width, self._height = self._interpret_size_values(width, height)
    self.resize(self._width, self._height)

    self._font = QFont(font_family, font_size)

    menu = self.menuBar()
    m_file = menu.addMenu("&File")
    m_file.addAction(qhelper.menu_item("E&xit", self, self.close))
    m_help = menu.addMenu("&Help")
    m_help.addAction(qhelper.menu_item("&Keys", self, self._on_help_keys))
    m_help.addAction(qhelper.menu_item("&About", self, self._on_help_about))

    self._main = MainWidget(self)
    self.setCentralWidget(self._main)
    self._main.textbox.returnPressed.connect(self._on_command)
    self._main.textbox.setVisible(False)

    self._images = list(images)
    self._count = len(self._images)
    self._image = None
    self._index = 0
    self._real_width = 0
    self._real_height = 0
    self._mode = MODE_NONE

    # Number of images to advance for bulk advancing
    self._advance_many = advance_many

    # Actions taken, marks made, etc.
    self._output = []

    self._keybinds = {}
    self._actions = collections.defaultdict(list)
    self._functions = {}

    self._add_keybind("Ctrl+q", self.close)
    self._add_keybind("Ctrl+w", self.close)
    self._add_keybind("Escape", self._key_on_escape)
    self._add_keybind("Left", self._key_prev_image)
    self._add_keybind("Right", self._key_next_image)
    self._add_keybind("Up", self._key_prev_many)
    self._add_keybind("Down", self._key_next_many)
    self._add_keybind("Shift+r", self._key_rename_image)
    self._add_keybind("Shift+d", self._key_delete_image)
    self._add_keybind("Shift+f", self._key_find_image)
    self._add_keybind("Shift+g", self._key_go_to_image)
    self._add_keybind(":", self._key_go_to_image)
    self._add_keybind("h", self._key_show_help)
    self._add_keybind("z", self._key_adjust, -1)
    self._add_keybind("c", self._key_adjust, 1)
    self._add_keybind("t", self._key_toggle_text)
    self._add_keybind("l", self._key_label)
    self._add_keybind("=", self._key_toggle_zoom)
    self._add_keybind("/", self._key_enter_command)
    self._add_keybind("_", self._key_zoom_out)
    self._add_keybind("+", self._key_zoom_in)
    for idx in range(1, 10):
      self._add_keybind(f"{idx}", self._key_mark_image, idx)

    # TODO: configure desired window size

    self.set_index(0)

    # TODO: implement text overlay

  def _interpret_size_values(self, width, height):
    "Interpret the width and height strings and get actual pixel values"
    avail_size = self.screen().availableGeometry()
    av_width = avail_size.width()
    av_height = avail_size.height()
    wvalue = valuehelper.interpret_amount(width, 0, av_width, astype=int)
    hvalue = valuehelper.interpret_amount(height, 0, av_height, astype=int)
    logger.debug("[%r, %r] of (%d, %d) -> (%d, %d)", width, height,
        av_width, av_height, wvalue, hvalue)
    return wvalue, hvalue

  def redraw(self):
    "Redraw the current image"
    path = self._images[self._index]
    mime, encoding = mimetypes.guess_type(path)
    if mime is None:
      raise ValueError(f"Image with unknown mimetype {path}")
    if encoding is not None:
      logger.error("File %r has encoding %r (mime %r)", path, encoding, mime)
      raise ValueError(f"Encodings not supported ({path!r} has {encoding})")
    mimecat, mimename = mime.split("/", 1)
    if mimecat == "image":
      self._image = QImage(path)
      self._main.canvas.setPixmap(QPixmap.fromImage(self._image))
      self._main.canvas.setAlignment(Qt.AlignCenter)
      self._main.show()
      # Drawing overlay text will likely involve subclassing QLabel and
      # overriding the draw function
      #painter = QPainter()
      #painter.begin(self)
      #painter.setFont(self._font)
      #painter.drawText(QPoint(0, 0), path)
      #painter.end()
    elif mimecat == "video":
      pass
    else:
      logger.warning("Unhandled mimetype %s for %s", mime, path)

  # Public slots for scripting use {{{0

  next_image = Slot(name="IMNextImage")(lambda self: self._next_image)
  prev_image = Slot(name="IMPrevImage")(lambda self: self._prev_image)
  next_many = Slot(name="IMNextMany")(lambda self: self._next_many)
  prev_many = Slot(name="IMPrevMany")(lambda self: self._prev_many)

  # TODO: IMGetIndex -> int
  # TODO: IMGoToIndex(int)
  # TODO: IMGoToName(str): go to first image with basename str
  # TODO: IMGetImagePath -> str
  # TODO: IMGetImageCount -> int

  # 0}}}

  index = property(lambda self: self._index)
  count = property(lambda self: self._count)
  path = property(lambda self: self._images[self._index])
  curr_size = property(lambda self: (0, 0)) # TODO
  real_size = property(lambda self: (self._real_width, self._real_height))
  win_size = property(lambda self: (self._width, self._height))
  mode = property(lambda self: self._mode)

  def set_index(self, idx):
    "Change the current index to the value given"
    if idx < 0 or idx >= self._count:
      raise ValueError(f"{idx} outside range [0, {self._count})")
    logger.debug("Index %d -> %d", self._index, idx)
    self._index = idx
    self.redraw()

  @property
  def textbox(self):
    "Get the input box element"
    return self._main.textbox

  def _show_textbox(self):
    "Ensure the textbox is both visible and has focus"
    if not self.textbox.isVisible():
      self.textbox.setVisible(True)
    if not self.textbox.hasFocus():
      self.textbox.setFocus()

  def _hide_textbox(self):
    "Ensure the textbox is both invisible and lacks focus"
    if self.textbox.hasFocus():
      self.textbox.clearFocus()
    if self.textbox.isVisible():
      self.textbox.setVisible(False)

  def _add_keybind(self, keys, func, *args, **kwargs):
    "Have the given key combination invoke the specified function"
    fname = lib.log.func_name(func)
    if keys not in self._keybinds:
      logger.debug("bind new %s to %s(*%r, **%r)", keys, fname, args, kwargs)
      kbinst = qhelper.KeyBind(keys, func, *args, **kwargs)
      self._keybinds[keys] = kbinst
      self.addAction(kbinst.get_action(self))
    else:
      logger.debug("bind %s to %s(*%r, **%r)", keys, fname, args, kwargs)
      self._keybinds[keys].bind(func, *args, **kwargs)

  def _advance_index(self, by):
    "Advance the image index by a specified number"
    self.set_index((self.index + by) % self.count)

  # Keybinds {{{0

  def _key_on_escape(self):
    "Called when the Escape key is pressed: de-focus the input, then exit"
    self._mode = MODE_NONE
    if self.textbox.hasFocus() or self.textbox.isVisible():
      self._hide_textbox()
    else:
      self.close()

  @_blocked_by_input
  def _key_prev_image(self):
    "Go to the previous image"
    self._advance_index(-1)

  @_blocked_by_input
  def _key_next_image(self):
    "Go to the next image"
    self._advance_index(1)

  @_blocked_by_input
  def _key_prev_many(self):
    "Go back several images"
    self._advance_index(-self._advance_many)

  @_blocked_by_input
  def _key_next_many(self):
    "Advance several images"
    self._advance_index(self._advance_many)

  @_blocked_by_input
  def _key_rename_image(self):
    "Enter the 'rename image' input mode"
    self._mode = MODE_RENAME
    self._show_textbox()

  @_blocked_by_input
  def _key_delete_image(self):
    "Mark the current image for deletion and advance to the next one"
    pass

  @_blocked_by_input
  def _key_find_image(self):
    "Enter the 'find image' input mode"
    self._mode = MODE_SET_IMAGE
    self._show_textbox()

  @_blocked_by_input
  def _key_go_to_image(self):
    "Enter the 'go to image' input mode"
    self._mode = MODE_GOTO
    self._show_textbox()

  @_blocked_by_input
  def _key_show_help(self):
    "Show the help text overlay"
    pass

  @_blocked_by_input
  def _key_adjust(self, amount):
    "Fine-adjust the current image's display size"
    pass

  @_blocked_by_input
  def _key_toggle_text(self):
    "Show or hide the image text overlay"
    pass

  @_blocked_by_input
  def _key_label(self):
    "Enter the 'label image' input mode"
    self._mode = MODE_LABEL
    self._show_textbox()

  @_blocked_by_input
  def _key_toggle_zoom(self):
    "Cycle through the zoom modes"
    pass

  @_blocked_by_input
  def _key_enter_command(self):
    "Enter the 'enter an arbitrary command' input mode"
    self._mode = MODE_COMMAND
    self._show_textbox()

  @_blocked_by_input
  def _key_zoom_out(self):
    "Reduce image size by a configurable amount"
    pass

  @_blocked_by_input
  def _key_zoom_in(self):
    "Increase image size by a configurable abount"
    pass

  @_blocked_by_input
  def _key_mark_image(self, number):
    "Mark an image with the given number"
    pass

  # 0}}}

  # Actions {{{0

  def _on_command(self): # input action
    "Called when a command is executed"
    mode = self._mode
    self._mode = MODE_NONE
    text = self.textbox.text()
    self._hide_textbox()

    logger.debug("_on_command: mode=%s text=%r", mode, text)
    if mode == MODE_RENAME:
      pass
    elif mode == MODE_GOTO:
      pass
    elif mode == MODE_SET_IMAGE:
      pass
    elif mode == MODE_LABEL:
      pass
    elif mode == MODE_COMMAND:
      pass
    else:
      logger.warning("Invalid mode %r (while executing %r)", mode, text)

  @Slot()
  def _on_help_keys(self): # menu action
    "Called when Help->Keys is invoked"
    return # TODO

  @Slot()
  def _on_help_about(self): # menu action
    "Called when Help->About is invoked"
    return # TODO

  # 0}}}

def gather_images(image_list, file_list, recurse=False, soft_errors=False):
  """
  Gather images from the specified items

  image_list    items passed directly on the command-line
  file_list     items passed via -F,--file
  recurse       scan directory contents recursively
  soft_errors   failure to load an argument won't terminate the program
  """
  inputs = []
  inputs.extend(iter_none(image_list))
  for file_path in iter_none(file_list):
    try:
      with open(file_path, "rt") as fobj:
        for line in fobj:
          inputs.append(line.rstrip(os.linesep))
    except IOError as err:
      if not soft_errors:
        raise
      logger.error("Error reading %s: %s", file_path, err)

  recurse_max = -1 if recurse else 1
  images = get_files(inputs, recurse_max, soft_errors=soft_errors)
  logger.debug("Scanned %d images", len(images))
  for idx, image in enumerate(images):
    logger.debug("Image %d/%d: %s", idx+1, len(images), image)
  return images

def main():
  ap = argparse.ArgumentParser(add_help=False)
  ag = ap.add_argument_group("image selection")
  ag.add_argument("images", nargs="*",
      help="files (or directories) to examine")
  ag.add_argument("-R", "--recurse", action="store_true",
      help="descend into directories recursively to find images")
  ag.add_argument("-F", "--file", metavar="PATH", action="append",
      help="read images from %(metavar)s")
  ag.add_argument("--ignore-errors", action="store_true",
      help="continue even if some of the images cannot be loaded")

  ag = ap.add_argument_group("display options")
  ag.add_argument("--width", default="100%",
      help="window width (default: %(default)s)")
  ag.add_argument("--height", default="100%",
      help="window height (default: %(default)s)")
  ag.add_argument("--font-family", default=FONT,
      help="override font (default: %(default)s)")
  ag.add_argument("--font-size", type=int, default=FONT_SIZE,
      help="override font size, in points (default: %(default)s)")
  ag.add_argument("--add-text", action="store_true",
      help="display image name and attributes over the image")
  ag.add_argument("--add-text-from", metavar="PROG",
      help="display text from program %(metavar)s (see --help-text-from)")

  ag = ap.add_argument_group("output control")
  ag.add_argument("-o", "--out", metavar="PATH",
      help="write actions to both stdout and %(metavar)s")
  ag.add_argument("-f", "--format", metavar="STR", default=LINE_FORMAT,
      help="output line format (default: %(default)r)")
  ag.add_argument("-a", "--append", action="store_true",
      help="append to the -o,--out file instead of overwriting")
  ag.add_argument("--text", action="store_true",
      help="output text instead of CSV")

  ag = ap.add_argument_group("keybind actions")
  ag.add_argument("--write1", metavar="PATH",
      help="write current image path to %(metavar)s on MARK-1")
  ag.add_argument("--write2", metavar="PATH",
      help="write current image path to %(metavar)s on MARK-2")
  ag.add_argument("--bind", action="append", metavar="KEY CMD", nargs=2,
      help="bind a keypress to invoke a shell command")

  ag = ap.add_argument_group("sorting")
  mg = ag.add_mutually_exclusive_group()
  mg.add_argument("-s", "--sort", metavar="KEY", default=SORT_NAME,
      choices=SORT_MODES,
      help="sort images by %(metavar)s: %(choices)s (default: %(default)s)")
  mg.add_argument("-S", "--sort-via", metavar="PROG",
      help="sort images by running %(metavar)s")
  ag.add_argument("-r", "--reverse", action="store_true",
      help="reverse sorting order; sort descending instead of ascending")

  ag = ap.add_argument_group("diagnostic control")
  ag.add_argument("-C", "--no-color", action="store_true",
      help="disable color logging")
  ag.add_argument("--logger", nargs=2, action="append",
      metavar=("LOGGER", "LEVEL"),
      help="configure a specific logger to have a specific level")

  ag = ap.add_argument_group("diagnostic levels")
  mg = ag.add_mutually_exclusive_group()
  mg.add_argument("-t", "--trace", action="store_const",
      const=logging.TRACE, dest="level", # pylint: disable=no-member
      help="enable trace-level output")
  mg.add_argument("-v", "--verbose", action="store_const",
      const=logging.DEBUG, dest="level",
      help="enable verbose output")
  mg.add_argument("-w", "--warning", action="store_const",
      const=logging.WARNING, dest="level",
      help="show only warnings and errors; hide informational messages")
  mg.add_argument("-e", "--error", action="store_const",
      const=logging.ERROR, dest="level",
      help="show only errors; hide all non-error messages")

  ag = ap.add_argument_group("other help text")
  ag.add_argument("-h", "--help", action="store_true",
      help="show this help text and exit")
  ag.add_argument("--help-text-from", action="store_true",
      help="show help text for --add-text-from")
  ag.add_argument("--help-write", action="store_true",
      help="show help text about mark operations")
  mg.add_argument("--help-sort", action="store_true",
      help="show help text about sorting and then exit")
  ag.add_argument("--help-keys", action="store_true",
      help="show usage and keypress behaviors and then exit")
  ag.add_argument("--help-all", action="store_true",
      help="show all help text and then exit")
  args, remainder = ap.parse_known_args()

  # Configure global logging levels
  if args.level is not None:
    logger.setLevel(args.level)
    for logger_name in lib.log.DeferredLogger.REGISTERED:
      logging.getLogger(logger_name).setLevel(args.level)

  # Configure per-logger levels
  if args.logger is not None:
    for logger_name, level_name in args.logger:
      if level_name.isdigit():
        logger_level = int(level_name)
      else:
        logger_level = lib.log.level_for(level_name)
      if logger_name in ("root", "main", "printer"):
        logger_inst = logger
      else:
        logger_inst = lib.log.get_logger(logger_name)
      logger_inst.setLevel(logger_level)

  # Lastly, enable colors (this currently affects all loggers)
  if not args.no_color:
    logger.enableColor()

  # Handle any help arguments
  want_help = any((args.help, args.help_text_from, args.help_write,
      args.help_sort, args.help_keys, args.help_all))
  want_help_basic = args.help or args.help_all
  want_help_text_from = args.help_text_from or args.help_all
  want_help_write = args.help_write or args.help_all
  want_help_sort = args.help_sort or args.help_all
  want_help_keys = args.help_keys or args.help_all
  if want_help:
    if want_help_basic:
      ap.print_help()
      sys.stderr.write(strtab.HELP_BASIC)
    else:
      ap.print_usage()
    if want_help_text_from:
      sys.stderr.write(strtab.HELP_TEXT_FROM)
    if want_help_write:
      sys.stderr.write(strtab.HELP_WRITE)
    if want_help_sort:
      sys.stderr.write(strtab.HELP_SORT)
    if want_help_keys:
      sys.stderr.write(strtab.HELP_KEYS)
    ap.exit(0)

  # Now we can actually start doing image processing!

  images = gather_images(args.images, args.file,
      recurse=args.recurse, soft_errors=args.ignore_errors)
  if not images:
    ap.error("No images specified")

  app = QApplication(remainder)
  window = ImageManager(images,
      width=args.width,
      height=args.height,
      font_family=args.font_family,
      font_size=args.font_size)
  window.show()
  sys.exit(app.exec())

if __name__ == "__main__":
  try:
    main()
  except ValueError as err:
    logger.exception(err)
    raise SystemExit(1)

# vim: set ts=2 sts=2 sw=2:
