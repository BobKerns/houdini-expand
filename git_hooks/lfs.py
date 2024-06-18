"""
Utilities for interacting with git-lfs.
"""

from pathlib import Path
import sys
from typing import BinaryIO
from subprocess import run

from git_hooks.install import get_git_filter
from git_hooks.utils import log


def read_lfs(f_input: BinaryIO) -> bytes:
    """
    Read the OID from stdin.
    """
    l1 = f_input.readline()
    l2 = f_input.readline()
    l3 = f_input.readline()
    return b'\n'.join([l1, l2, l3])

def smudge_via_lfs(oid: bytes, file: Path,
                   f_output: BinaryIO=sys.stdout.buffer):
    """
    Smudge the file using the git-lfs command.
    """
    _, smudge = get_git_filter('lfs', file)
    run(smudge.split(' '),
        input=oid,
        stdout=f_output,
        check=True)
    log.debug('Smudged %s via git-lfs', file)
