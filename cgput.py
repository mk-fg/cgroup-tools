#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
parser = argparse.ArgumentParser(
	description='Put given tids/pids into a control group.')
parser.add_argument('cgroup', help='Cgroup name.')
parser.add_argument('ids', nargs='+', help='Process/thread ids.')
optz = parser.parse_args()

import itertools as it, operator as op, functools as ft
from glob import iglob
import os, sys

dst_set = set(it.imap(os.path.realpath, it.chain(
	iglob('/sys/fs/cgroup/*/{}/tasks'.format(optz.cgroup)),
	iglob('/sys/fs/cgroup/*/{}/cgroup.procs'.format(optz.cgroup)) )))
if not dst_set:
	parser.error('Cgroup not found in any hierarchy: {}'.format(optz.cgroup))

for dst, tid in it.product(dst_set, optz.ids):
	open(dst, 'wb').write('{}\n'.format(tid))
