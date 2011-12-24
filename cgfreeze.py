#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

import argparse
parser = argparse.ArgumentParser(
	description='Put/ specified cgroup(s) in/out-of the freezer.')
parser.add_argument('-u', '--unfreeze',
	action='store_true', help='Unfreeze the cgroup(s).')
parser.add_argument('-c', '--check',
	action='store_true', help='Just get the state of a specified cgroup(s).')
parser.add_argument('cgroups', nargs='+', help='Cgroup(s) to operate on.')
argz = parser.parse_args()

import os, sys

for cg in argz.cgroups:
	cg_state = '/sys/fs/cgroup/freezer/tagged/{}/freezer.state'.format(cg)
	if not os.path.exists(cg_state):
		print('{}: inaccessible'.format(cg), file=sys.stderr)
		continue
	if argz.check:
		print('{}: {}'.format(cg, open(cg_state).read().strip()))
	else:
		state = b'FROZEN\n' if not argz.unfreeze else b'THAWED\n'
		open(cg_state, 'wb').write(state)
