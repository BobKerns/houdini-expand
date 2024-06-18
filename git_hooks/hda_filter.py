#!/usr/bin/env python3

import sys

from git_hooks.lfs import read_lfs, smudge_via_lfs

if sys.version_info[0] != 3 or sys.version_info[1] < 12:
    print(f'This script requires Python 3.12 or later: {sys.version_info[1]}', file=sys.stderr)
    sys.exit(1)

from typing import BinaryIO, Literal, TypedDict, cast
from pathlib import Path
from subprocess import run
from tempfile import NamedTemporaryFile, TemporaryDirectory

from git_hooks.utils import log
from git_hooks.install import get_git_filter, get_hotl
from git_hooks.encode import DecoderFailure, decode_stream, encode_directory, read_header, smudge_via_decode

def clean(file: Path, f_input: BinaryIO=sys.stdin.buffer, f_output: BinaryIO=sys.stdout.buffer):
    """
    Clean the file using the hotl command.
    """
    hotl = get_hotl()
    clean, _ = get_git_filter('lfs', file)
    with NamedTemporaryFile(prefix='lfs') as fout:
        with file.open('rb') as fin:
            run(clean.split(' '), check=True, stdin=fin, stdout=fout)
            with open(fout.name, 'rb') as fin:
                    data = fin.read()
                    f_output.write(data)
    if hotl is not None:
        with TemporaryDirectory() as tmpdir:
            with NamedTemporaryFile(prefix=f'{file.stem}_', suffix=file.suffix) as blob:
                data = f_input.read()
                blob.write(data)
                run([hotl, '-t', tmpdir, blob.name], check=True)
                dir = Path(tmpdir)
                encode_directory(dir, dir, f_output)
    log.debug(f'Cleaned {file} to {dir}')

def smudge(file: Path,
           f_input: BinaryIO=sys.stdin.buffer,
           f_output: BinaryIO=sys.stdout.buffer):
    """
    Smudge the file using the hotl command.
    """
    oid = read_lfs(f_input)
    hotl = get_hotl()
    if hotl is None:
        # If we don't have Houdini available, we get the binary from git-lfs.
        return smudge_via_lfs(oid, file, f_output)
    else:
        try:
            with decode_stream(f_input) as tmpdir:
                run([hotl, '-t', tmpdir, file], check=True)
        except DecoderFailure:
            # If the decode fails, we get the binary from git-lfs.
            smudge_via_lfs(oid, file, f_output)
