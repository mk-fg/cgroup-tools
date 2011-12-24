#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
parser = argparse.ArgumentParser(
	description='Put given pids into a control group.')
parser.add_argument('cgroup', help='Cgroup name.')
parser.add_argument('pids', nargs='+', help='Process ids.')
optz = parser.parse_args()

from glob import iglob
import os, sys

dst_set = set(map( os.path.realpath,
	iglob('/sys/fs/cgroup/*/{}/tasks'.format(optz.cgroup)) ))
if not dst_set:
	parser.error('Cgroup not found in any hierarchy: {}'.format(optz.cgroup))

for pid in optz.pids:
	for dst in dst_set:
		open(dst, 'wb').write('{}\n'.format(pid))
