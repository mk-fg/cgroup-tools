#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

import argparse
parser = argparse.ArgumentParser(description='List PIDs, belonging to a specified cgroups.')
parser.add_argument('cgroups', nargs='+', help='Cgroup(s) to operate on.')
argz = parser.parse_args()

cg_root = '/sys/fs/cgroup'

import itertools as it, operator as op, functools as ft
from os.path import join, isdir
from glob import glob
import os, sys

pids = set()

listdirs = lambda path: it.ifilter( isdir,
	it.imap(ft.partial(join, path), os.listdir(path)) )
collect_pids = lambda path:\
	pids.update(int(line.strip()) for line in open(join(path, 'tasks')))

def collect_pids_recurse(path):
	collect_pids(path)
	for sp in listdirs(path): collect_pids_recurse(sp)

for rc in os.listdir(cg_root):
	for cg_name in argz.cgroups:
		cg = 'tagged/{}'.format(cg_name)
		cg_path = glob(join(cg_root, rc, cg))\
			or glob(join(cg_root, rc, cg.replace('/', '.')))\
			or glob('{}.*'.format(join(cg_root, rc, cg.replace('/', '.'))))
		if not cg_path: continue # could be present in other rc's
		for path in cg_path: collect_pids_recurse(path)

sys.stdout.write(''.join(it.imap('{}\n'.format, pids)))
