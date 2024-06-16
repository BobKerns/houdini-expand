#!/usr/bin/env python3

import sys

if sys.version_info[0] != 3 or sys.version_info[1] < 12:
    print(f'This script requires Python 3.12 or later: {sys.version_info[1]}', file=sys.stderr)
    sys.exit(1)

from typing import Literal
import logging
from pathlib import Path

logging.basicConfig(level='DEBUG')
log = logging.getLogger(Path(__name__).stem)

CONFIG_HOTL = 'hdafilter.hotl'

type FilterCmd = Literal['clean', 'smudge', 'search']

platform_locations = {
    "win32": {

    },
    "darwin": {
        "/Applications/Houdini": {
            "glob": "Houdini*",
            "subpath": "Frameworks/Houdini.framework/Versions/Current/Resources/bin/hotl"
        }
    },
    "linux": {
    }
}

def locations():
    """
    Yields all potential hotl locations on the current platform.
    """
    return (
        hotl
        for dir, spec in platform_locations[sys.platform].items()
        for hotl in sorted(Path(dir).glob(spec['glob']))
    )

type GitArg = str|Path|int

def git(cmd: str, *args: str):
    from subprocess import run
    import shutil
    git_cmd = shutil.which('git')
    log.debug('%s %s %s', git_cmd, cmd, ' '.join(str(arg) for arg in args))
    return run([git_cmd, cmd, *(str(arg) for arg in args)],
                check=True,
                text=True,
                stderr=sys.stderr,
                )

def search_hotl():
    print('Searching for hotl command.', file=sys.stderr)
    for hotl in locations():
        if hotl.exists():
            print(f'Found hotl: {hotl}')
    git('config', CONFIG_HOTL, hotl)
            
    for dir, spec in platform_locations[sys.platform].items():
                houdinis = Path(dir).glob(spec['glob'])
                print('Found Houdini installations:')
                for houdini in houdinis:
                    hotl = houdini / spec['subpath']
                    print(f'. {hotl}: {hotl.exists()}')

def main(command: FilterCmd):
    match command:
        case 'search':
            search_hotl()
        case _:
            print(f"Unknown command: {command}", file=sys.stderr)
            exit(1)

if __name__ == '__main__':
    from argparse import ArgumentParser, Namespace
    parser = ArgumentParser()
    subcmds = parser.add_subparsers(dest='command')
    clean_parser = subcmds.add_parser('clean')
    smudge_parser = subcmds.add_parser('smudge')
    search_parser = subcmds.add_parser('search')
    args = parser.parse_args()
    main(**vars(args))