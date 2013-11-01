cgroup-tools
--------------------

A set of tools to work with cgroup tree and processes classification/QoS,
according to it.

More (of a bit outdated) info can be found
[here](http://blog.fraggod.net/2011/2/cgroups-initialization-libcgroup-and-my-ad-hoc-replacement-for-it).

Main script there - cgconf - allows to use YAML like this to configure initial
cgroup hierarcy:

	path: /sys/fs/cgroup

	defaults:
	  _tasks: root:wheel:664
	  _admin: root:wheel:644
	  freezer:

	groups:

	  # base:
	  #   _default: true # to put all pids here initially
	  #   cpu.shares: 1000
	  #   blkio.weight: 1000

	  user.slice:
	    cpu:
	      cfs_quota_us: 1_500_000
	      cfs_period_us: 1_000_000

	  tagged:
	    cave:
	      _tasks: root:paludisbuild
	      _admin: root:paludisbuild
	      cpu:
	        shares: 100
	        cfs_quota_us: 100_000
	        cfs_period_us: 250_000
	      blkio.weight: 100
	      memory.soft_limit_in_bytes: 2G
	    desktop:
	      roam:
	        _tasks: root:users
	        cpu.shares: 300
	        blkio.weight: 300
	        # memory.soft_limit_in_bytes: 2G
	      java:
	        _tasks: root:users
	        cpu.shares: 100
	        blkio.weight: 100
	        memory.soft_limit_in_bytes: 1G

(from laptop with [dying
fan](http://blog.fraggod.net/2013/11/01/software-hacks-to-fix-broken-hardware-laptop-fan.html),
hence cpu bandwidth limits)

And then something like `cgrc <tagged-name> <cmd> <args...>` to run anything put
inside these.

Other tools allow waiting for one cgroup threads to finish before proceeding and
put stuff running there on hold easily.

cgconf and cgrc turn out to be surprisingly still useful despite systemd adding
knobs to control cgroup resource limits (but not all of them, and spread over
lot of small files, which are pain if you need a big picture of e.g. weights)
and systemd-run, which hides i/o of whatever it runs in systemd slices.


TODO
--------------------

* check out [peo3/cgroup-utils](https://github.com/peo3/cgroup-utils) and
  whether I can rebase this stuff on top of it
