# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Generates test runner factory and tests for performance tests."""

import json
import fnmatch
import logging
import os
import shutil

from devil.android import device_list
from devil.android import device_utils
from pylib import constants
from pylib.perf import test_runner
from pylib.utils import test_environment


def _GetAllDevices(active_devices, devices_path):
  # TODO(rnephew): Delete this when recipes change to pass file path.
  if not devices_path:
    logging.warning('Known devices file path not being passed. For device '
                    'affinity to work properly, it must be passed.')
  try:
    if devices_path:
      devices = [device_utils.DeviceUtils(s)
                 for s in device_list.GetPersistentDeviceList(devices_path)]
      if not devices and active_devices:
        logging.warning('%s is empty. Falling back to active devices.',
                        devices_path)
        devices = active_devices
    else:
      logging.warning('Known devices file path not being passed. For device '
                      'affinity to work properly, it must be passed.')
      devices = active_devices
  except IOError as e:
    logging.error('Unable to find %s [%s]', devices_path, e)
    devices = active_devices
  return sorted(devices)


def _GetStepsDictFromSingleStep(test_options):
  # Running a single command, build the tests structure.
  steps_dict = {
    'version': 1,
    'steps': {
        'single_step': {
          'device_affinity': 0,
          'cmd': test_options.single_step
        },
    }
  }
  return steps_dict


def _GetStepsDict(test_options):
  if test_options.single_step:
    return _GetStepsDictFromSingleStep(test_options)
  if test_options.steps:
    with file(test_options.steps, 'r') as f:
      steps = json.load(f)

      # Already using the new format.
      assert steps['version'] == 1
      return steps


def Setup(test_options, active_devices):
  """Create and return the test runner factory and tests.

  Args:
    test_options: A PerformanceOptions object.

  Returns:
    A tuple of (TestRunnerFactory, tests, devices).
  """
  # TODO(bulach): remove this once the bot side lands. BUG=318369
  constants.SetBuildType('Release')
  if os.path.exists(constants.PERF_OUTPUT_DIR):
    shutil.rmtree(constants.PERF_OUTPUT_DIR)
  os.makedirs(constants.PERF_OUTPUT_DIR)

  # Before running the tests, kill any leftover server.
  test_environment.CleanupLeftoverProcesses(active_devices)

  # We want to keep device affinity, so return all devices ever seen.
  all_devices = _GetAllDevices(active_devices, test_options.known_devices_file)

  steps_dict = _GetStepsDict(test_options)
  sorted_step_names = sorted(steps_dict['steps'].keys())

  if test_options.test_filter:
    sorted_step_names = fnmatch.filter(sorted_step_names,
                                       test_options.test_filter)

  flaky_steps = []
  if test_options.flaky_steps:
    with file(test_options.flaky_steps, 'r') as f:
      flaky_steps = json.load(f)

  def TestRunnerFactory(device, shard_index):
    if str(device) in active_devices:
      return test_runner.TestRunner(
          test_options, device, shard_index, len(all_devices),
          steps_dict, flaky_steps)
    return None

  return (TestRunnerFactory, sorted_step_names, all_devices)
