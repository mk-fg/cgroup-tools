#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from __future__ import print_function

# No argparser here - it's just not worth it.
# Usage:
#  cgrc -g group < cmd...
#  cgrc -g group cmd...
#  cgrc -q group cmd...
#  cgrc.group cmd...
# If "group" starts with /, it won't be prefixed with "tagged/"

cgname_tpl = 'tagged/{}' # template for cgroup path
tasks = '/sys/fs/cgroup/*/{}/cgroup.procs' # path to resource controllers' pseudo-fs'es

import os, sys

cmd_base = sys.argv[0].rsplit('.py', 1)[0]
if '.' in cmd_base:
	cgname, cmd = cmd_base.split('.', 1)[-1], sys.argv[1:]
else:
	cmd_base, cmd = (list(), sys.argv[1:])\
		if not sys.argv[1].startswith('-s ') else\
			( ''.join(open(sys.argv[2]).readlines()[1:]).strip().split(),
				sys.argv[1].split()[1:] + sys.argv[3:] )
	if cmd[0] in ['-g', '-q']:
		opt, cgname, cmd = cmd[0], cmd[1], cmd[2:]
		if opt == '-q':
			import subprocess
			subprocess.check_call(['cgwait', '-e', cgname], close_fds=True)
	else: cgname, cmd = cmd[0], cmd[1:]
	cmd = cmd_base + cmd

cgname = cgname_tpl.format(cgname)\
	if not cgname.startswith('/') else cgname.lstrip('/')

from glob import glob

cg_pid = '{}\n'.format(os.getpid())
for tasks in glob(tasks.format(cgname))\
		+ glob(tasks.format(cgname.replace('/', '.'))):
	with open(tasks, 'wb') as dst: dst.write(cg_pid)

os.execvp(cmd[0], cmd)
