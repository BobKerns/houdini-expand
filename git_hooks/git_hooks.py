#!/usr/bin/env python3
"""
Command line interface for git_hooks.
"""

import sys
from pathlib import Path

if sys.version_info[0] != 3 or sys.version_info[1] < 12:
    print(f'This script requires Python 3.12 or later: {sys.version_info[1]}', file=sys.stderr)
    sys.exit(1)

dir = Path(__file__).parent
if (dir / 'git_hooks.py').is_file():
    # We are being run from the git_hooks source directory.
    dir = dir.parent
elif (dir / 'git_hooks').is_dir():
    # We are being run from an installation on the PATH.
    pass
else:
    print(f'Cannot find the git_hooks package in {dir}', file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(dir))

from git_hooks.cmdline import cmdline

if __name__ == '__main__':
    cmdline()
