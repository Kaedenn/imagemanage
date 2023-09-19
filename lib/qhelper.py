#!/usr/bin/env python

"""
Various helper functions and whatnot to assist with PySide6 stuff
"""

import logging

from PySide6.QtGui import QAction

import lib.log
lib.log.hotpatch(logging)
logger = lib.log.DeferredLogger(__name__)

class KeyBind:
  """
  A key combination to function(s) association.

  This class attempts to augment the normal QAction keybind logic with the
  ability to bind multiple independent functions to a single key combination.
  """
  def __init__(self, keys, *functions):
    "Constructor; see help(type(self)) for usage"
    self._keys = keys
    self._functions = list(functions)
    self._action = None

  keys = property(lambda self: self._keys)
  functions = property(lambda self: tuple(self._functions))

  def bind(self, function, *args, **kwargs):
    "Have the keybind call the function with the specified arguments (if any)"
    @functools.wraps(function)
    def wrapper(*fargs, **fkwargs):
      return function(*fargs, *args, **fkwargs, **kwargs)
    self._functions.append(wrapper)

  def get_action(self, host):
    "Create and return the QAction for this keybind"
    if self._action is None:
      self._action = QAction("", host, triggered=lambda: self())
      self._action.setShortcut(self._keys)
    return self._action

  def __call__(self, *args, **kwargs):
    "Manually invoke all of the bound functions with optional arguments"
    for func in self._functions:
      logger.debug("invoke %s: %s(*%s, **%s)", self._keys,
          lib.log.func_name(func), args, kwargs)
      func(*args, **kwargs)

def menu_item(label, host, on_trigger, shortcuts=None):
  """
  Create a QAction having the given behavior.

  label         menu entry label with an optional & accelerator key
  host          the host class (typically just the caller's `self`)
  on_trigger    function to call when this action is invoked
  shortcuts     key combination(s) (str or list of strs) to trigger this action
  """
  action = QAction(label, host, triggered=on_trigger)
  if shortcuts is not None:
    if isinstance(shortcuts, str):
      action.setShortcut(shortcuts)
    else:
      action.setShortcuts(shortcuts)
  return action

# vim: set ts=2 sts=2 sw=2:
