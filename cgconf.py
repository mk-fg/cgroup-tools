#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

####################

import os, sys
conf = '{}.yaml'.format(os.path.realpath(__file__).rsplit('.', 1)[0])

####################


import argparse
parser = argparse.ArgumentParser(
	description='Tool to create cgroup hierarchy and perform a basic tasks classification.')
parser.add_argument('-c', '--conf', default=conf, help='Configuration file (default: %(default)s).')
parser.add_argument('-r', '--reset', action='store_true',
	help='Put all processes into a default cgroup, not just non-classified ones.')
parser.add_argument('-p', '--dry-run', action='store_true', help='Just show what has to be done.')
parser.add_argument('--debug', action='store_true', help='Verbose operation mode.')
argz = parser.parse_args()

import logging
logging.basicConfig(level=logging.DEBUG if argz.debug else logging.INFO)
log = logging.getLogger()

import itertools as it, operator as op, functools as ft
from subprocess import Popen, PIPE, STDOUT
from os.path import join, isdir, isfile
import yaml


_default_perms = _default_rcs = _default_cg = _mounts = None


def init_rc(rc, rc_path):
	log.debug('Initializing path for rc ({}): {}'.format(rc, rc_path))

	mkdir_chk = not isdir(join(conf['path'], rc))
	if mkdir_chk:
		log.debug('Creating rc path: {}'.format(rc_path))
		if not argz.dry_run: os.mkdir(rc_path)

	global _mounts
	if _mounts is None:
		_mounts = set(it.imap(op.itemgetter(4), it.ifilter(
			lambda line: line[7] == 'cgroup', it.imap(
				op.methodcaller('split'), open('/proc/self/mountinfo') ))))
		log.debug('Found mounts: {}'.format(_mounts))

	if mkdir_chk or rc_path not in _mounts:
		if os.path.islink(rc_path):
			log.debug(( 'Symlink in place of rc-path (rc: {}),'
				' skipping (assuming hack or joint mount): {}' ).format(rc, rc_path))
		else:
			mount_cmd = 'mount', '-t', 'cgroup', '-o', rc, rc, rc_path
			log.debug('Mounting rc path: {} ({})'.format(rc_path, ' '.join(mount_cmd)))
			if not argz.dry_run:
				if Popen(mount_cmd).wait():
					raise RuntimeError( 'Failed to mount'
						' rc path: {}, command: {}'.format(rc_path, mount_cmd) )
		_mounts.add(rc_path)


def parse_perms(spec):
	uid = gid = mode = None
	if not spec: return uid, gid, mode
	uid, spec = spec.split(':', 1)
	if uid:
		try: uid = int(uid)
		except ValueError:
			import pwd
			uid = pwd.getpwnam(uid).pw_uid
	try: gid, spec = spec.split(':', 1)
	except ValueError: return uid, gid, mode
	if gid:
		try: gid = int(gid)
		except ValueError:
			import grp
			gid = grp.getgrnam(gid).gr_gid
	if spec: mode = int(spec, 8)
	return uid, gid, mode

def merge_perms(set1, set2):
	return tuple(
		tuple(
			(val1 if val1 is not None else val2)
				for val1, val2 in it.izip(sset1, sset2) )
		for sset1, sset2 in it.izip(set1, set2) )

_units = dict( Ki=2**10, Mi=2**20,
	Gi=2**30, K=1e3, M=1e6, G=1e9 )
def interpret_val(val):
	try:
		num, units = val.split(' ')
		num = int(num) * _units[units]
	except (AttributeError, IndexError, ValueError, KeyError): return val
	else: return num


def configure(path, settings, perms):
	global _default_perms
	if _default_perms is None:
		try: def_tasks = conf['defaults']['_tasks']
		except KeyError: def_tasks = None
		try: def_admin = conf['defaults']['_admin']
		except KeyError: def_admin = None
		_default_perms = tuple(it.imap(parse_perms, (def_tasks, def_admin)))
		log.debug('Default permissions: {}'.format(_default_perms))

	perms = merge_perms(it.imap(parse_perms, perms), _default_perms)
	log.debug('Setting permissions for {}: {}'.format(path, perms))
	if not argz.dry_run:
		for node in it.ifilter(isfile, it.imap(
				ft.partial(join, path), os.listdir(path) )):
			os.chown(node, *perms[1][:2])
			os.chmod(node, perms[1][2])
		os.chown(join(path, 'tasks'), *perms[0][:2])
		os.chmod(join(path, 'tasks'), perms[0][2])

	log.debug('Configuring {}: {}'.format(path, settings))
	if not argz.dry_run:
		for node, val in settings.viewitems():
			val = interpret_val(val)
			open(join(path, node), 'wb').write(b'{}\n'.format(val))


def classify(cg_path, tasks):
	if not argz.dry_run:
		for task in tasks:
			try:
				if not open('/proc/{}/cmdline'.format(task)).read(): continue # kernel thread
				with open(join(cg_path, 'tasks'), 'wb') as ctl: ctl.write(b'{}\n'.format(task))
			except (OSError, IOError): pass # most likely dead pid


def settings_inline(rc_dict):
	rc_inline = dict()
	for rc,settings in rc_dict:
		if isinstance(settings, dict):
			for k,v in settings.viewitems():
				rc_inline['{}.{}'.format(rc, k)] = v
		elif settings is None: rc_inline[rc] = dict()
		else: rc_inline[rc] = settings
	return rc_inline

def settings_dict(rc_inline):
	rc_dict = dict(rc_inline)
	for rc_spec,val in rc_dict.items():
		if '.' in rc_spec:
			rc, param = rc_spec.split('.', 1)
			rc_dict[rc] = rc_dict.get(rc, dict())
			rc_dict[rc][param] = val
			del rc_dict[rc_spec]
		elif val is None: rc_dict[rc_spec] = dict()
	return rc_dict

def settings_for_rc(rc, settings):
	return dict( ('{}.{}'.format(rc, k), v)
		for k,v in settings.viewitems() )

def path_for_rc(rc, name):
	return name # blkio is pseudo-hierarhical these days
	# return name if rc != 'blkio' else name.replace('/', '.')

def parse_cg(name='', contents=dict()):
	global _default_rcs
	if _default_rcs is None:
		_default_rcs = settings_inline(it.ifilter(
			lambda v: not v[0].startswith('_'),
			conf.get('defaults', dict()).viewitems() ))
		log.debug('Default settings:\n{}'.format(
			'\n'.join('  {} = {}'.format(k,v) for k,v in
				sorted(_default_rcs.viewitems(), key=op.itemgetter(0))) ))
	if contents is None: contents = dict()

	log.debug('Processing group {}'.format(name or '(root)'))
	if name.endswith('_') or not contents\
			or filter(lambda k: k.startswith('_') or '.' in k, contents):
		name = name.rstrip('_')
		contents = settings_inline(contents.viewitems())

		settings = _default_rcs.copy()
		settings.update(
			settings_inline(it.ifilter(
				lambda v: not v[0].startswith('_'),
				contents.viewitems() )) )
		settings = settings_dict(settings.viewitems())

		for rc,settings in settings.viewitems():
			log.debug('Configuring {}: {} = {}'.format(name, rc, settings))
			rc_path, rc_name = join(conf['path'], rc), path_for_rc(rc, name)
			init_rc(rc, rc_path)
			cg_path = join(rc_path, rc_name)
			if not isdir(cg_path):
				log.debug('Creating cgroup path: {}'.format(cg_path))
				if not argz.dry_run:
					cg_base = rc_path
					for slug in rc_name.split('/'):
						cg_base = join(cg_base, slug)
						if not isdir(cg_base): os.mkdir(cg_base)
			configure( cg_path, settings_for_rc(rc, settings),
				(contents.get('_tasks', ''), contents.get('_admin', '')) )
			if contents.get('_default'):
				global _default_cg
				if _default_cg is not None and _default_cg != name:
					raise ValueError('There can be only one default cgroup')
				log.debug('Populating default cgroup: {}'.format(cg_path))
				if not argz.dry_run:
					read_pids = lambda path: (int(line.strip()) for line in open(join(path, 'tasks')))
					pids = set( read_pids(rc_path)
						if not argz.reset else it.chain.from_iterable(
							read_pids(root) for root,dirs,files in os.walk(rc_path)
							if 'tasks' in files and root != cg_path ) )
					classify(cg_path, pids)
				_default_cg = name

	else:
		for subname, contents in contents.viewitems():
			parse_cg(join(name, subname), contents)


conf = yaml.load(open(conf).read().replace('\t', '  '))
parse_cg(contents=conf['groups'])
