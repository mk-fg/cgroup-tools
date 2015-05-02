#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
parser = argparse.ArgumentParser(
	description='List pids (tgids), belonging to a specified cgroups.')
parser.add_argument('cgroups', nargs='+', help='Cgroup(s) to operate on.')
parser.add_argument('--no-checks',
	action='store_true', help='Do not perform sanity checks on pid sets.')
argz = parser.parse_args()

cg_root = '/sys/fs/cgroup'

import itertools as it, operator as op, functools as ft
from os.path import join, isdir
from glob import glob
import os, sys

listdirs = lambda path: it.ifilter( isdir,
	it.imap(ft.partial(join, path), os.listdir(path)) )
collect_pids = lambda path, pids_set:\
	pids_set.update(int(line.strip()) for line in open(join(path, 'cgroup.procs')))

def collect_pids_recurse(path, pids_set):
	collect_pids(path, pids_set)
	for sp in listdirs(path): collect_pids_recurse(sp, pids_set)

pids = dict()

for rc in os.listdir(cg_root):
	pids[rc] = pids_set = set()
	for cg_name in argz.cgroups:
		cg = 'tagged/{}'.format(cg_name)
		cg_path = glob(join(cg_root, rc, cg))\
			or glob(join(cg_root, rc, cg.replace('/', '.')))\
			or glob('{}.*'.format(join(cg_root, rc, cg.replace('/', '.'))))
		if not cg_path:
			del pids[rc]
			continue
		for path in cg_path: collect_pids_recurse(path, pids_set)

if not argz.no_checks:
	for (ak, a), (bk, b) in it.combinations(pids.items(), 2):
		pids_diff = a.symmetric_difference(b)
		if not pids_diff: continue
		print( 'Difference between rc pid sets {}/{}: {}'\
			.format(ak, bk, ' '.join(map(bytes, pids_diff))), file=sys.stderr )

pids_all = reduce(op.or_, pids.viewvalues(), set())
sys.stdout.write(''.join(it.imap('{}\n'.format, pids_all)))
