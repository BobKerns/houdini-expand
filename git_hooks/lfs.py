"""
Utilities for interacting with git-lfs.
"""

from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
from typing import BinaryIO
from subprocess import run

from git_hooks.install import get_git_filter
from git_hooks.utils import log

def read_lfs(f_input: BinaryIO) -> bytes:
    """
    Read the LFS OID from the input.
    """
    l1 = f_input.readline()
    l2 = f_input.readline()
    l3 = f_input.readline()
    return b'\n'.join([l1, l2, l3])

def write_lfs(file: Path, f_output: BinaryIO):
    """
    Write the LFS OID to the output.
    """
    lfs = get_git_filter('lfs', file)
    if lfs is None:
        log.debug('No LFS filter for %s', file)
        return
    lfs_clean = lfs['clean']
    with NamedTemporaryFile(prefix='lfs') as fout:
        with file.open('rb') as fin:
            run(lfs_clean.split(' '), check=True, stdin=fin, stdout=fout)
            with open(fout.name, 'rb') as fin:
                    data = fin.read()
                    f_output.write(data)
def smudge_via_lfs(oid: bytes, file: Path,
                   f_output: BinaryIO=sys.stdout.buffer):
    """
    Smudge the file using the git-lfs command.
    """
    f = get_git_filter('lfs', file)
    if f is None:
        log.debug('No LFS filter for %s', file)
    else:
        smudge = f['smudge']
        run(smudge.split(' '),
            input=oid,
            stdout=f_output,
            check=True)
        log.debug('Smudged %s via git-lfs', file)
