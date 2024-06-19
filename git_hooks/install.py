"""
Commands to install, configure, an inspect the git hooks.
"""

from pathlib import Path
from typing import Optional, TypedDict, cast
from shutil import copyfile, copytree, rmtree, which
import os
from subprocess import CalledProcessError

from git_hooks.attributes import GitAttributesFile
from git_hooks.utils import log
from git_hooks.git import git, GitArg
from git_hooks.version import IDENT, __version__
from git_hooks.filters import find_path_dir, locations

CONFIG_HOTL = 'filter.hda.hotl'

class Filter(TypedDict):
    """
    Filter information.
    """
    clean: str
    smudge: str
    required: bool

def install(dir: Optional[Path] = None, *,
            hotl: Optional[Path]=None,
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
        for h in locations('hda', 'clean'):
            log.debug(f'Checking {h}')
            if h.is_file():
                log.info(f'Found hotl: {h}')
                config(CONFIG_HOTL, h, local=local)
                hotl = h
                break
        else:
            log.error('No hotl command found. Is Houdini installed?')
            return None
    elif hotl.is_file():
        log.info(f"Using {hotl} as the hotl command.")
        config(CONFIG_HOTL, hotl, local=local)
    else:
        log.error('Command not found: %s', hotl)
        exit(1)
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
        if script.parent.parent.samefile(dir):
            log.info('Script is already installed in %s', dir)
        else:
            lib_loc = dir / script.stem
            log.info('Installing script %s to %s', script, script_loc)
            copyfile(script, script_loc)
            log.info('Installing library to %s', lib_loc)
            if lib_loc.exists():
                rmtree(lib_loc)
            copytree(srcdir, lib_loc, dirs_exist_ok=True)
            script_loc.chmod(0o755)
    if which(script.name) is None:
        log.warning('Script not on the path. Add %s to the path.', dir)
    config('filter.hda.clean', f'{script.name} clean %f', local=local)
    config('filter.hda.smudge', f'{script.name} smudge %f', local=local)
    config('filter.hda.required', True, local=local)
    attrs = GitAttributesFile.load(gitattributes)
    attrs['*.hda'].set_attributes('-text', 'lockable', filter='hda', diff='hda', merge='hda')
    attrs.save(gitattributes)
    return None

def config(key: str, value: Optional[GitArg]=None, *,
           local: bool=False,
           match: bool=False
           ) -> str|None:
    """
    Get a config value from git.
    """
    args: tuple[str, ...] = ('--local',) if local else ('--global',)
    if value is None:
        if match:
            args = ('--get-regexp',)
            key = key.replace('.', '[.]').replace('*', '.*')
        else:
            args = ('--get',)
    else:
        rest: list[str]
        match value:
            case True:
                rest = ['true']
            case False:
                rest = ['false']
            case None:
                args = (*args, '--unset')
                rest = []
            case _:
                rest = [str(value)]
        git('config', *args, key, *rest)
        return None
    try:
        return git('config', *args, key).strip()
    except CalledProcessError as ex:
        if ex.returncode == 1:
            return None
        raise ex

def list_hotl():
    """
    List the potential hotl commands and whether they exist.
    """
    for hotl in locations('hda', 'hotl'):
        print(f'. {hotl}: {hotl.exists()}')

def status(local: bool=False):
    """
    Show the current configuration
    """
    hotl = config(CONFIG_HOTL)
    if hotl is None:
        hotl = config(CONFIG_HOTL)
    info: list[tuple[str, str|Path|None, int]] = []
    def show(key: str,
             value: str|Path|None='',
             indent:int = 2):
        info.append((key, value, indent))
    show('Version', __version__)
    if IDENT:
        show('Commit ID', IDENT)
    show('Install location', Path(__file__).resolve().parent)
    show('hotl command', hotl)
    for filter in ('lfs', 'hda'):
        show(f'Filter {filter}', '', 0)
        lines = config(f'filter.{filter}.*', match=True)
        if lines is not None:
            for line in lines.splitlines():
                if line:
                    key, value = line.split(' ', 1)
                    show(f'  {key}', value)

    keywidth = max(len(key) for key, _, _ in info)
    for key, value, indent in info:
        if indent == 0:
            print(f'{key}:')
        else:
            print(f'{'':{indent}}{key:>{keywidth}}: {value}')
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
                print(f'    {key}: {attrs}')
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
        log.error('No hotl command configured. Is Houdini installed?')
        return None
    return Path(hotl)

def get_git_filter(filter: str, file: Optional[Path] = None) -> Filter|None:
    """
    Get the git-lfs commands.

    PARAMS:
    filter: The filter name.
    file: The filename to substitute into the command line.
    """
    lines = config(f'filter.{filter}.*', match=True)
    if lines is None:
        return None
    lines = (l.strip() for l in lines.splitlines())
    f = {
        key.split('.')[2]: value
        for line in lines
        if line
        for key, value in [line.split(' ', 1)]
    }
    return cast(Filter, f)

def subst_file(cmd: str, file: Path):
    """
    Substitute the filename into the command line.
    """
    return str.replace(cmd, '%f', str(file))
