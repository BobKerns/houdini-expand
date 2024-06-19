"""
Installation and tool loctions.
"""

from collections.abc import Generator
import os
from pathlib import Path
import sys
from threading import local
from typing import Literal, NotRequired, Optional, TypedDict

from git_hooks.utils import log

type LocationKind = Literal['clean', 'smudge']

class BaseFilterInfo(TypedDict):
    """
    Candidate location for the hotl command.
    """
    filter: str
    kind: LocationKind

class InternalFilterInfo(BaseFilterInfo):
    """
    Candidate location for an internal filter.

    These are commands that may not be on the path, and should
    be searched for.

    The search is done by globbing, i.e.
    dir/glob/subpath, where glob can have wildcards.
    """
    dir: str
    glob: NotRequired[str]
    subpath: NotRequired[str]
    args: str

class ExternalFilterInfo(BaseFilterInfo):
    """
    Candidate location for an external filter.

    These are commands that are expected to be on the path
    """
    command: str
    args: str

type FilterInfo = InternalFilterInfo | ExternalFilterInfo

### Where to look for the hotl command on different platforms.
platform_locations: dict[str, list[FilterInfo]] = {
    "win32": [
        {
            "filter": "hda",
            "dir": "C:/Program Files/Side Effects Software/",
            "glob": "Houdini*",
            "subpath": "bin/hotl.exe",
            "kind": 'clean',
            "args": '-t %d %f',
        },
        {
            "filter": "hda",
            "dir": "C:/Program Files/Side Effects Software/",
            "glob": "Houdini*",
            "subpath": "bin/hotl.exe",
            "kind": 'smudge',
            "args": '-l %d %f',
        }
    ],
    "darwin": [
        {
            "filter": "hda",
            "dir": "/Applications/Houdini",
            "glob": "Houdini*/Frameworks/Houdini.framework/Versions/Current",
            "subpath": "Resources/bin/hotl",
            "kind": "clean",
            "args": '-t %d %f',
        },
        {
            "filter": "hda",
            "dir": "/Applications/Houdini",
            "glob": "Houdini*/Frameworks/Houdini.framework/Versions/Current",
            "subpath": "Resources/bin/hotl",
            "kind": "smudge",
            "args": '-l %d %f',
        }
    ],
    "linux": [
        {
            "filter": "hda",
            "dir": "/opt",
            "glob": "hfs*",
            "subpath": "bin/hotl",
            "kind": "clean",
            "args": '-t %d %f',
        },
        {
            "filter": "hda",
            "dir": "/opt",
            "glob": "hfs*",
            "subpath": "bin/hotl",
            "kind": "smudge",
            "args": '-l %d %f',
        }
    ]
}

def filter_info(filter: Optional[str] = None,
                kind: Optional[str] = None,
                ):
    """
    Yields all potential filter dependency locations

    PARAMS:
    filter: The filter to find.
    kind: The kind of filter dependency to find.
    """
    return (
        spec
        for spec in platform_locations[sys.platform]
        if filter is None or spec['filter'] == filter
        if kind is None or spec['kind'] == kind
    )

def locations(filter: Optional[str] = None,
              kind: Optional[str] = None,
              directory: bool = False,
              exists: bool = False,
              ) -> Generator[Path, None, None]:
    """
    Yields all potential hotl locations on the current platform.
    """
    return (
        file if subpath is None else file / subpath
        for spec in filter_info(filter, kind)
        for dir in [spec.get('dir', None)]
        if dir is not None
        for glob in [spec.get('glob', None)]
        if glob is not None
        for subpath in [spec.get('subpath', None)]
        for file in sorted(Path(dir).glob(glob), reverse=True)
        if not exists or file.exists()
        if not directory or file.is_dir()
        if directory or file.is_file()
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
