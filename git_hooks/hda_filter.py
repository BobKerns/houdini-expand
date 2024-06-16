#!/usr/bin/env python3

import sys

if sys.version_info[0] != 3 or sys.version_info[1] < 12:
    print(f'This script requires Python 3.12 or later: {sys.version_info[1]}', file=sys.stderr)
    sys.exit(1)

from typing import Literal, Optional, TypedDict
import logging
from pathlib import Path
from shutil import which
from subprocess import run, CompletedProcess, CalledProcessError
from tempfile import NamedTemporaryFile, TemporaryDirectory

logging.basicConfig(level=logging.WARNING,
                    handlers=[logging.StreamHandler(sys.stderr)],
)
log = logging.getLogger(Path(__file__).stem)

CONFIG_HOTL = 'hdafilter.hotl'

type FilterCmd = Literal['clean', 'smudge', 'search', 'show', 'list']

class Location(TypedDict):
    """
    Candidate location for the hotl command.
    """
    dir: str
    glob: str
    subpath: str

### Where to look for the hotl command on different platforms.
platform_locations: dict[str, Location] = {
    "win32": [
        {
            "dir": "C:/Program Files/Side Effects Software/",
            "glob": "Houdini*",
            "subpath": "bin/hotl.exe"
        }
    ],
    "darwin": [
        {
            "dir": "/Applications/Houdini",
            "glob": "Houdini*/Frameworks/Houdini.framework/Versions/Current",
            "subpath": "/Resources/bin/hotl"
        }
    ],
    "linux": [
        {
            "dir": "/opt",
            "glob": "hfs*",
            "subpath": "bin/hotl"
        }
    ]
}

def locations():
    """
    Yields all potential hotl locations on the current platform.
    """
    return (
        (hotl / loc['subpath'], loc)
        for loc in platform_locations[sys.platform]
        for hotl in sorted(Path(loc['dir']).glob(loc['glob']), reverse=True)
    )

type GitArg = str|Path|int

def git(cmd: str, *args: str):
    """
    Run a git command and return the output.
    """
    git_cmd = which('git')
    log.debug('%s %s %s', git_cmd, cmd, ' '.join(str(arg) for arg in args))
    proc: CompletedProcess = run([git_cmd, cmd, *(str(arg) for arg in args)],
                check=True,
                text=True,
                capture_output=True,
                )
    err = proc.stderr
    if err:
        print(err, file=sys.stderr)
    return proc.stdout

def configure():
    """
    Search for the hotl command and configure it in the git config.
    """
    print('Searching for hotl command.', file=sys.stderr)
    for hotl, _ in locations():
        if hotl.exists():
            print(f'Found hotl: {hotl}')
    git('config', CONFIG_HOTL, hotl)
    return hotl

def config(key: str) -> str|None:
    """
    Get a config value from git.
    """
    try:
        return git('config', '--get', key).strip()
    except CalledProcessError as ex:
        if ex.returncode == 1:
            return None
        raise ex

def list_hotl():
    """
    List the potential hotl commands and whether they exist.
    """
    for hotl, _ in locations():
        print(f'. {hotl}: {hotl.exists()}')

def show_config():
    """
    Show the current configuration
    """
    hotl = config(CONFIG_HOTL)
    if hotl is None:
        configure()
        hotl = config(CONFIG_HOTL)
    clean, smudge = get_git_lfs()
    def show(key, value):
        print(f'{key:>14}: {value}')
    show('hotl', hotl)
    show('git-lfs clean', clean)
    show('git-lfs smudge', smudge)

def get_hotl() -> Path:
    """
    Get the hotl command from the git config.
    """
    hotl = config(CONFIG_HOTL)
    if not hotl:
         hotl = configure()
    if not hotl:
        print('No hotl command configured.', file=sys.stderr)
        exit(1)
    return Path(hotl)

def get_git_lfs(file: Path = Path('%f')) -> tuple[str, str]:
    """
    Get the git-lfs commands.
    """
    clean = config('filter.lfs.clean')
    smudge = config('filter.lfs.smudge')
    if clean is None or smudge is None:
        print('git-lfs not configured.', file=sys.stderr)
        exit(1)
    return subst_file(clean, file), subst_file(smudge, file)

def subst_file(cmd: str, file: Path):
    """
    Substitute the filename into the command line.
    """
    return str.replace(cmd, '%f', str(file))

def clean(file: Path):
    """
    Clean the file using the hotl command.
    """
    hotl = get_hotl()
    clean, _ = get_git_lfs(file)
    with TemporaryDirectory() as tmpdir:
        with NamedTemporaryFile(prefix='lfs') as fout:
            with file.open('rb') as fin:
                run(clean.split(' '), check=True, stdin=fin, stdout=fout)
            with open(fout.name, 'rb') as fin:
                data = fin.read()
                print(data.decode())
            run([hotl, file, tmpdir], check=True)
            print(f'Cleaned {file} to {tmpdir}')

def main(file: Optional[str]=None, *, command: FilterCmd, debug: bool = False):
    if debug:
        log.setLevel('DEBUG')
    match command:
        case 'search':
            configure()
        case 'show':
              show_config()
        case 'list':
            list_hotl()
        case 'clean':
            clean(Path(file))
        case _:
            print(f"Unknown command: {command}", file=sys.stderr)
            exit(1)

if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('--debug', '-d',
                        action='store_true',
                        help='Enable debug logging')
    subcmds = parser.add_subparsers(dest='command')
    clean_parser = subcmds.add_parser('clean',
                                      description='Turn the HDA into textual form for git storage')
    clean_parser.add_argument('file',
                                type=Path,
                                help='The file to clean')
    smudge_parser = subcmds.add_parser('smudge',
                                       description='Turn the HDA into binary form for Houdini')
    smudge_parser.add_argument('file',
                                 type=Path,
                                 help='The file to smudge')
    config_parser = subcmds.add_parser('configure',
                                       description='Search for Houdini installations and configure the hotl command')
    list_parser = subcmds.add_parser('list',
                                     description='List all Houdini installations')
    show_parser = subcmds.add_parser('show',
                                     description='Show the current hotl command')
    args = parser.parse_args()
    main(**vars(args))