"""
Utilitiies for git hooks.
"""

from pathlib import Path
from typing import Optional, Union, Literal, overload
import logging
import sys

logging.basicConfig(level=logging.INFO,
                    handlers=[logging.StreamHandler(sys.stderr)],
)
log = logging.getLogger(Path(__file__).stem)

@overload
def path(path: Path|str|None, *,
            optional: Literal[True],
            reason: Optional[str]=None,
            ) -> Path|None:
    ...
@overload
def path(path: Path|str|None, *,
            optional: Literal[False],
            reason: Optional[str]=None,
            ) -> Path:
    ...
@overload
def path(path: Path|str|None, *,
            optional: Optional[bool]=False,
            reason: Optional[str]=None,
            ) -> Path:
    ...
def path(path: Path|str|None, *,
            optional: Optional[bool]=False,
            reason: Optional[str]=None,
            ) -> Path|None:
    """
    Require a path.
    """
    if path is None:
        if optional:
            return None
        if reason is not None:
            raise ValueError(reason)
        raise ValueError('No file specified')
    return Path(path)
