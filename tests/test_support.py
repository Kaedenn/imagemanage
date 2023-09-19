#!/usr/bin/env python3

"""
Test suite for imagemanage.py supporting functions
"""

import os
import pytest
import imagemanage

def test_format_timestamp(): # TODO
  pass

def test_format_size():
  func = imagemanage.format_size
  assert func(1) == "1.0 B"
  assert func(1, base=10) == "1.0 B"
  assert func(1, places=0) == "1 B"
  assert func(1, places=0, base=10) == "1 B"
  assert func(1024) == "1.0 KB"
  assert func(1000, base=10) == "1.0 KiB"
  assert func(1024, places=0) == "1 KB"
  assert func(1000, places=0, base=10) == "1 KiB"
  assert func(1000, places=0, base=10, format="{num}{suffix}") == "1KiB"
  assert func(1024**2) == "1.0 MB"
  assert func(1024**3) == "1.0 GB"
  assert func(1024**4) == "1.0 TB"
  assert func(1024**5) == "1.0 PB"
  assert func(1024**6) == "1024.0 PB"

  num = 1000**3; num /= 1024; num /= 1024 # ensure the operations are identical
  assert func(num, places=None) == f"{num} B"

def test_iterate_from():
  base_seq = list(range(10))
  for start in range(len(base_seq))):
    result = list(imagemanage.iterate_from(base_seq, start))
    result_r = list(imagemanage.iterate_from(base_seq, start - len(base_seq)))
    assert set(result) == set(base_seq)
    assert set(result) == set(result_r)
    assert result == result_r

  def assert_asserts(sequence, start_index):
    "Wrapper function to ensure func(sequence, start_index) errors"
    try:
      list(imagemanage.iterate_from(sequence, start_index))
    except AssertionError:
      assert True, "{sequence} {start_index} asserted as expected"
    else:
      assert False, "{sequence} {start_index} did not assert"

  assert_asserts(base_seq, 12)
  assert_asserts(base_seq, -12)

# vim: set ts=2 sts=2 sw=2:
