#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import os, sys, struct

len_fmt = '!I'
len_fmt_bytes = struct.calcsize(len_fmt)
cg_root = '/sys/fs/cgroup'


### Fork child pid that will be cgroup-confined asap

(cmd_r, cmd_w), (cmd_start_r, cmd_start_w) = os.pipe(), os.pipe()
cmd_pid = os.fork()

if not cmd_pid:
	os.close(cmd_w), os.close(cmd_start_r)
	cmd_r, cmd_start_w = os.fdopen(cmd_r, 'rb', 0), os.fdopen(cmd_start_w, 'wb', 0)

	def cmd_main():
		# Read list of cgroups to use
		data_len = cmd_r.read(len_fmt_bytes)
		if len(data_len) != len_fmt_bytes: sys.exit(1)
		data_len, = struct.unpack(len_fmt, data_len)
		cmd = cmd_r.read(data_len).splitlines()
		cmd_r.close()
		if not cmd: sys.exit(0) # parent pid failed
		cg_paths, cmd = cmd[:-1], cmd[-1]
		cmd = map(lambda arg: arg.decode('hex'), cmd.split('\0'))
		assert cg_paths, cg_paths

		# cgroups are applied here so that there won't
		#  be any delay or other stuff between that and exec
		cg_pid = '{}\n'.format(os.getpid())
		for tasks in cg_paths:
			with open(tasks, 'wb') as dst: dst.write(cg_pid)
		cmd_start_w.write('.')
		cmd_start_w.flush()
		cmd_start_w.close()
		os.execvp(cmd[0], cmd)

	cmd_main()
	os.abort() # should never get here

os.close(cmd_r), os.close(cmd_start_w)
cmd_w, cmd_start_r = os.fdopen(cmd_w, 'wb', 0), os.fdopen(cmd_start_r, 'rb', 0)


### Parent pid

import itertools as it, operator as op, functools as ft
from os.path import join, exists, dirname, isdir
from collections import OrderedDict
from glob import iglob
from time import time

page_size = os.sysconf('SC_PAGE_SIZE')
page_size_kb = page_size // 1024
user_hz = os.sysconf('SC_CLK_TCK')
sector_bytes = 512

def num_format(n, decimals=3):
	n, ndec = list(bytes(n)), ''
	if '.' in n:
		ndec = n.index('.')
		n, ndec = n[:ndec], '.' + ''.join(n[ndec+1:][:decimals])
	res = list()
	while n:
		for i in xrange(3):
			res.append(n.pop())
			if not n: break
		if not n: break
		res.append('_')
	return ''.join(reversed(res)) + ndec

def dev_resolve( major, minor,
		log_fails=True, _cache = dict(), _cache_time=600 ):
	ts_now, dev_cached = time(), False
	while True:
		if not _cache: ts = 0
		else:
			dev = major, minor
			dev_cached, ts = (None, _cache[None])\
				if dev not in _cache else _cache[dev]
		# Update cache, if necessary
		if ts_now > ts + _cache_time or dev_cached is False:
			_cache.clear()
			for link in it.chain(iglob('/dev/mapper/*'), iglob('/dev/sd*'), iglob('/dev/xvd*')):
				link_name = os.path.basename(link)
				try: link_dev = os.stat(link).st_rdev
				except OSError: continue # EPERM, EINVAL
				_cache[(os.major(link_dev), os.minor(link_dev))] = link_name, ts_now
			_cache[None] = ts_now
			continue # ...and try again
		if dev_cached: dev_cached = dev_cached.replace('.', '_')
		elif log_fails:
			log.warn( 'Unable to resolve device'
				' from major/minor numbers: {}:{}'.format(major, minor) )
		return dev_cached or None

def main(args=None):
	import argparse
	parser = argparse.ArgumentParser(
		description='Tool to measure resources consumed'
			' by a group of processes, no matter how hard they fork.'
		' Does that by creating a temp cgroup and running passed command there.')
	parser.add_argument('cmdline', nargs='+',
		help='Command to run and any arguments for it.')
	parser.add_argument('-g', '--cgroup',
		default='bench', metavar='{ /path | tagged-path }',
		help='Hierarchy path to create temp-cgroup under'
				' ("/" means root cgroup, default: %(default)s).'
			' Any missing path components will be created.'
			' If relative name is specified, it will be interpreted from /tagged path.')
	parser.add_argument('-c', '--rcs',
		default='cpuacct, blkio, memory', metavar='rc1[, rc2, ...]',
		help='Comma-separated list of rc hierarchies to get metrics from (default: %(default)s).'
			' Should have corresponding path mounted under {}.'.format(cg_root))
	parser.add_argument('-d', '--debug', action='store_true', help='Verbose operation mode.')
	opts = parser.parse_args(sys.argv[1:] if args is None else args)

	global log
	import logging
	logging.basicConfig(level=logging.DEBUG if opts.debug else logging.INFO)
	log = logging.getLogger()

	# Check all rc tasks-file paths
	cg_subpath = 'tmp.{}'.format(cmd_pid)
	cg_tasks, cg_path = OrderedDict(), join('tagged', opts.cgroup).lstrip('/')
	for rc in map(bytes.strip, opts.rcs.split(',')):
		tasks = join(cg_root, rc, cg_path, cg_subpath, 'tasks')
		assert '\n' not in tasks, repr(tasks)
		os.makedirs(dirname(tasks))
		assert exists(tasks), tasks
		cg_tasks[rc] = tasks

	# Append cmdline, send data to child
	data = '\n'.join( cg_tasks.values()
		+ ['\0'.join(map(lambda arg: arg.encode('hex'), opts.cmdline))] )
	cmd_w.write(struct.pack(len_fmt, len(data)) + data)
	cmd_w.flush()

	# Wait for signal to start counting
	mark = cmd_start_r.read(1)
	ts0 = time()
	assert mark == '.', repr(mark)
	cmd_start_r.close()

	pid, status = os.waitpid(cmd_pid, 0)
	ts1 = time()

	err = status >> 8
	if status & 0xff:
		print('Unclean exit of child pid due to signal: {}'.format((status & 0xff) >> 1))
		err = err or 1

	# Make sure everything finished running there
	leftovers = set()
	for tasks in cg_tasks.values():
		with open(tasks) as src:
			leftovers.update(map(int, src.read().splitlines()))
	if leftovers:
		print( 'Main pid has finished, but cgroups have leftover threads'
			' still running: {}'.format(', '.join(map(bytes, leftovers))), file=sys.stderr )
		err = err or 1

	# Collect/print accounting data
	acct = OrderedDict()
	acct['cmd'] = ' '.join(opts.cmdline)
	acct['wall_clock'] = '{:.3f}'.format(ts1 - ts0)
	acct['exit_status'] = '{} {}'.format(status >> 8, status & 0xff >> 1)

	acct_srcs = OrderedDict()
	for cg_path in map(dirname, cg_tasks.viewvalues()):
		for p in os.listdir(cg_path): acct_srcs[p] = join(cg_path, p)

	acct_nums = OrderedDict([
		('cpuacct', ['usage', 'usage_percpu']),
		('memory', [
			'max_usage_in_bytes',
			'memsw.max_usage_in_bytes',
			'kmem.max_usage_in_bytes',
			'kmem.tcp.max_usage_in_bytes']) ])
	for rc, metrics in acct_nums.viewitems():
		for p in metrics:
			p = '{}.{}'.format(rc, p)
			if p not in acct_srcs: continue
			with open(acct_srcs[p]) as src:
				numbers = map(int, src.read().strip().split())
				acct[p] = ' '.join(map(num_format, numbers))

	for p in 'time sectors io_merged io_serviced io_wait_time'.split():
		p = 'blkio.{}'.format(p)
		try: src = acct_srcs[p]
		except KeyError: pass
		else:
			with open(src) as src: src = src.read().splitlines()
			for line in src:
				line = line.split()
				if not line or line[0] == 'Total': continue
				t = None
				try: dev, t, v = line
				except ValueError: dev, v = line
				dev = dev_resolve(*map(int, dev.split(':')))
				if not dev: continue
				label = '{}[{}]'.format(p, dev)
				if t: label += '[{}]'.format(t)
				acct[label] = num_format(int(v))

	for k, v in acct.viewitems():
		print('{}: {}'.format(k, v), file=sys.stderr)

	# Cleanup tmp dirs
	leftovers = set()
	for tasks in cg_tasks.values():
		tasks_dir = dirname(tasks)
		try: os.rmdir(tasks_dir)
		except (OSError, IOError): leftovers.add(tasks_dir)
	if leftovers:
		print( 'Leftover cgroup dirs remaining:{}\n'\
			.format('\n  '.join([''] + sorted(leftovers))), file=sys.stderr )
		err = err or 1

	return err

if __name__ == '__main__': sys.exit(main())
