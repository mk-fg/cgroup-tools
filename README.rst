cgroup-tools
------------

**DEPRECATION NOTICE**:

  | These scripts are useless on a modern linux with unified cgroup-v2 hierarchy.
  | On a systemd-enabled machine, use "systemd-run --scope" instead.
  | See also: `mk-fg/fgtk#cgrc tool <https://github.com/mk-fg/fgtk#cgrc>`_

A set of tools to work with cgroup tree and process classification/QoS
according to it.

More (of a bit outdated) info can be found `in a blog post here
<http://blog.fraggod.net/2011/2/cgroups-initialization-libcgroup-and-my-ad-hoc-replacement-for-it>`_.

Main script there - cgconf - allows to use YAML like this to configure initial
cgroup hierarcy like this::

  path: /sys/fs/cgroup

  defaults:
    _tasks: root:wheel:664
    _admin: root:wheel:644
    # _path: root:root:755 # won't be chown/chmod'ed, if unset
    freezer:

  groups:

    # Must be applied to root cgroup
    memory.use_hierarchy: 1

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
          memory.soft_limit_in_bytes: 2G

        de_misc:
          memory.soft_limit_in_bytes: 700M
          memory.limit_in_bytes: 1500M

      vm:
        quasi:
        misc:
          cpu.shares: 200
          blkio.weight: 100
          memory.soft_limit_in_bytes: 1200M
          memory.limit_in_bytes: 1500M

      bench:
        # Subdir for adhoc cgroups created by user
        tmp:
          # Corresponding pw_gid will be used, if "user:" is specified
          # Specs like "user", ":group:770" or "::775" are all valid.
          _tasks: 'fraggod:'
          _admin: 'fraggod:'
          _path: 'fraggod:'
          # These will be initialized as dirs with proper uid/gid, but no stuff applied there
          cpuacct:
          memory:
          blkio:
        # Limits that groups in tmp/ can't transcend
        cpu.shares: 500
        blkio.weight: 500
        memory.soft_limit_in_bytes: 300M
        memory.limit_in_bytes: 500M

And then something like ``cgrc <tagged-name> <cmd> <args...>`` to run anything
inside these (can also be used in shebang with -s, with cmd from stdin, etc).

Other tools allow waiting for threads within some cgroup to finish before
proceeding (cgwait), put stuff running there on hold easily (cgfreeze) and run
stuff in temp-cgroup, reporting accounting data for it afterwards (cgtime).

cgconf and cgrc turn out to be surprisingly useful still, despite systemd adding
knobs to control cgroup resource limits (but not all of them, and spread over
lot of small files, which are pain if you need a big picture of e.g. weights)
and systemd-run, which hides i/o of whatever it runs in systemd slices.
