"""
Version information for the git_hooks package.
"""

from typing import NamedTuple

class VersionInfo(NamedTuple):
    major: int
    minor: int
    micro: int
    releaselevel: str
    serial: int

VERSION_INFO = VersionInfo(major=0, minor=0, micro=0, releaselevel='final', serial=0)
if VERSION_INFO.releaselevel != 'final':
    if VERSION_INFO.serial == 0:
        releaselevel = f'.{VERSION_INFO.releaselevel}'
    else:
        releaselevel = f'.{VERSION_INFO.releaselevel}-{VERSION_INFO.serial}'
else:
    releaselevel = ''

VERSION = f'{VERSION_INFO.major}.{VERSION_INFO.minor}.{VERSION_INFO.micro}{releaselevel}'
ident = '$Id$'
if len(ident) == 4:
    IDENT=''
else:
    IDENT = ident.strip('$').split(' ')[1]
