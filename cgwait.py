#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

####################

poll_interval = 5
timeout = 0

####################

import argparse
parser = argparse.ArgumentParser(description='Wait for certain cgroup events.')
parser.add_argument('-i', '--poll-interval', type=float, default=poll_interval,
	help='task-files polling interval (default: %(default)ss).')
parser.add_argument('-t', '--timeout', type=float, default=timeout,
	help='Timeout for operation (default: %(default)ss).'
		' Results in non-zero exit code, 0 or negative to disable.')
parser.add_argument('-e', '--empty', action='store_true',
	help='Wait for cgroup(s) to become empty (default).')
parser.add_argument('--debug', action='store_true', help='Verbose operation mode.')
parser.add_argument('cgroups', nargs='+', help='Cgroup(s) to operate on.')
argz = parser.parse_args()

if not argz.empty: argz.empty = True
if argz.debug:
	import logging
	logging.basicConfig(level=logging.DEBUG if argz.debug else logging.INFO)
	log = logging.getLogger()

import itertools as it, operator as op, functools as ft
from glob import glob
from time import time, sleep

tasks = list(
	glob('/sys/fs/cgroup/*/{}/tasks'.format(cg))
		+ glob('/sys/fs/cgroup/*/{}/tasks'.format(cg.replace('/', '.')))
	for cg in it.imap('tagged/{}'.format, argz.cgroups) )
for task_file in tasks: # sanity check
	if not task_file: parser.error('No task-files found for cgroup: {}')
tasks = set(it.chain.from_iterable(tasks))

if argz.debug:
	log.debug('Watching task-files: {}, timeout: {}'.format(' '.join(tasks), timeout))

done = False
deadline = time() + argz.timeout if argz.timeout > 0 else 0
while True:
	if argz.empty:
		for task_file in tasks:
			if open(task_file).read().strip():
				if argz.debug: log.debug('task-file isnt empty: {}'.format(task_file))
				break
		else: done = True
	if done: break
	if deadline and time() > deadline: exit(2)
	sleep(argz.poll_interval)
