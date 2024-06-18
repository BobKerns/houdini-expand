"""
Routines for interfacing with git.
"""

from pathlib import Path
from subprocess import run, CompletedProcess
from shutil import which
import sys

from git_hooks.utils import log

type GitArg = str|Path|int

def git(cmd: str, *args: GitArg):
    """
    Run a git command and return the output.
    """
    git_cmd = which('git')
    if git_cmd is None:
        raise Exception('git not found')
    log.debug('%s %s %s', git_cmd, cmd, ' '.join(str(arg) for arg in args))
    cmdline = [git_cmd, cmd, *(str(arg) for arg in args)]
    proc: CompletedProcess = run(cmdline,
                check=True,
                text=True,
                capture_output=True,
                )
    err = proc.stderr
    if err:
        print(err, file=sys.stderr)
    return proc.stdout
