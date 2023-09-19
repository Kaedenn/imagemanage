#!/usr/bin/env python

"""
Functions to simplify dealing with certain values and value types.
"""

def interpret_amount(value, minval, maxval, astype=float):
  "Interpret a value (as a string) as a number between minval and maxval"
  if value is None:
    return maxval
  if value.endswith("%"):
    result = int(value[:-1]) / 100 * (maxval - minval) + minval
    return astype(result)
  return astype(value)

def iter_none(sequence):
  "Iterate over a sequence, allowing for the sequence to be None"
  if sequence is not None:
    yield from sequence

# vim: set ts=2 sts=2 sw=2:
