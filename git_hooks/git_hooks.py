#!/usr/bin/env python3
"""
Command line interface for git_hooks.
"""

import sys
from pathlib import Path

if sys.version_info[0] != 3 or sys.version_info[1] < 12:
    print(f'This script requires Python 3.12 or later: {sys.version_info[1]}', file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))

from git_hooks.cmdline import cmdline

if __name__ == '__main__':
    cmdline()
