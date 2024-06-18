"""
Commands to install, configure, an inspect the git hooks.
"""



from enum import nonmember
from pathlib import Path
from typing import Optional, TypedDict
from shutil import copyfile, copytree, which
import os
import sys
from subprocess import CalledProcessError

from git_hooks.attributes import GitAttributesFile
from git_hooks.utils import log
from git_hooks.git import git, GitArg
from git_hooks.version import IDENT, __version__

CONFIG_HOTL = 'hdafilter.hotl'


class Location(TypedDict):
    """
    Candidate location for the hotl command.
    """
    dir: str
    glob: str
    subpath: str

### Where to look for the hotl command on different platforms.
platform_locations: dict[str, list[Location]] = {
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
            "subpath": "Resources/bin/hotl"
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
        hotl / loc['subpath']
        for loc in platform_locations[sys.platform]
        for hotl in sorted(Path(loc['dir']).glob(loc['glob']), reverse=True)
    )


def find_path_dir() -> Path:
    """
    Find the path directory where we can install our scripts.
    """
    path = os.getenv('PATH', None)
    if path is None:
        raise Exception('No PATH environment variable')
    for dir in path.split(os.pathsep):
        dir = Path(dir)
        if dir.is_dir() and os.access(dir, os.W_OK):
            return dir
    else:
        log.warning('No writable directory in PATH' )
        return Path.home() / '.local/bin'


def install(dir: Optional[Path] = None, *,
            hotl: Optional[str]=None,
            local: bool=False):
    """
    Search for the hotl command and configure the hda_filter into the git config.

    PARAMS:
    dir: [optional] The directory to install this script. It should be on the path.
    hotl: [optional] The hotl command to use. Defaults to searching for the newest Houdini installation.
    local: [optional] Set the configuration locally rather than globally.
    """
    log.debug('Searching for hotl command.')
    if hotl is None:
        for h in locations():
            if h.is_file():
                log.info(f'Found hotl: {h}')
                config(CONFIG_HOTL, hotl, local=local)
    elif Path(hotl).is_file():
        config(CONFIG_HOTL, hotl, local=local)
    else:
        log.warning('No hotl command found. Is Houdini installed?')
    toplevel = git('rev-parse', '--show-toplevel').strip()
    if toplevel is None:
        raise Exception("The current directory is not within a git working tree.")
    toplevel = Path(toplevel)
    gitattributes = toplevel / '.gitattributes'
    if dir is None or not os.access(dir, os.W_OK):
        dir = find_path_dir()
    if dir is not None and not os.access(dir, os.W_OK):
        dir = None
    script = Path(__file__).with_stem('git_hooks')
    srcdir = script.parent
    if dir is not None:
        script_loc = dir / script.name
        lib_loc = dir / script.stem
        log.info('Installing script %s to %s', script, script_loc)
        copyfile(script, script_loc)
        log.info('Installing library to %s', lib_loc)
        copytree(srcdir, lib_loc, dirs_exist_ok=True)
        script_loc.chmod(0o755)
    if which(script.name) is None:
        log.warning('Script not on the path. Add %s to the path.', dir)
    config('filter.hda.clean', 'hda_filter.py clean %f', local=local)
    config('filter.hda.smudge', 'hda_filter.py smudge %f', local=local)
    config('filter.hda.required', True, local=local)
    attrs = GitAttributesFile.load(gitattributes)
    attrs['*.hda'].set_attributes('-text', 'lockable', filter='hda', diff='hda', merge='hda')
    attrs.save(gitattributes)
    return None

def config(key: str, value: Optional[GitArg]=None, *,
           local: Optional[bool]=False) -> str|None:
    """
    Get a config value from git.
    """
    if value is not None:
        match value:
            case True:
                value = 'true'
            case False:
                value = 'false'
        args = ('--local',) if local else ('--global',)
        git('config', *args, key, value)
        return None
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
    for hotl in locations():
        print(f'. {hotl}: {hotl.exists()}')


def status(local: bool=False):
    """
    Show the current configuration
    """
    hotl = config(CONFIG_HOTL)
    if hotl is None:
        install()
        hotl = config(CONFIG_HOTL)
    clean, smudge = get_git_filter('lfs')

    info: list[tuple[str, str]] = []
    def show(key, value):
        info.append((key, value))
    show('Version', __version__)
    if IDENT:
        show('Commit ID', IDENT)
    show('Install location', Path(__file__).resolve().parent)
    show('hotl command', hotl)
    show('git-lfs clean', clean)
    show('git-lfs smudge', smudge)
    show('filter.hda.clean', config('filter.hda.clean', local=local))
    show('filter.hda.smudge', config('filter.hda.smudge', local=local))
    show('filter.hda.required', config('filter.hda.required', local=local))

    keywidth = max(len(key) for key, _ in info)
    for key, value in info:
        print(f'{key:>{keywidth}}: {value}')
    try:
        toplevel = Path(git('rev-parse', '--show-toplevel').strip())
    except:
        raise Exception("The current directory is not within a git working tree.")

    git_dir = Path(git('rev-parse', '--git-dir').strip())
    if not git_dir.is_absolute():
        git_dir = toplevel / git_dir
    def show_gitattributes(file: Path):
        if file.exists():
            print(f'In {file.relative_to(toplevel)}:')
        attrs_file = GitAttributesFile.load(file)
        for key, attrs in attrs_file:
            if 'filter' in attrs or 'diff' in attrs or 'merge' in attrs:
                print(f'{key}: {attrs}')
    show_gitattributes(toplevel / '.gitattributes')
    show_gitattributes(git_dir / 'info/gitattributes')

def get_hotl() -> Path|None:
    """
    Get the hotl command from the git config.
    """
    hotl = config(CONFIG_HOTL)
    if not hotl:
         hotl = install()
    if not hotl:
        print('No hotl command configured. Is Houdini installed?',
              file=sys.stderr)
        return None
    return Path(hotl)

def get_git_filter(filter: str, file: Optional[Path] = None) -> tuple[str, str]:
    """
    Get the git-lfs commands.

    PARAMS:
    filter: The filter name.
    file: The filename to substitute into the command line.
    """
    clean = config(f'filter.{filter}.clean')
    smudge = config(f'filter.{filter}.smudge')
    if clean is None or smudge is None:
        print('git-lfs not configured.', file=sys.stderr)
        exit(1)
    if file is None:
        return clean, smudge
    return subst_file(clean, file), subst_file(smudge, file)

def subst_file(cmd: str, file: Path):
    """
    Substitute the filename into the command line.
    """
    return str.replace(cmd, '%f', str(file))