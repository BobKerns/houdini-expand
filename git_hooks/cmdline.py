#!/usr/bin/env python3
"""
Command line interface for git_hooks.
"""

import sys
from pathlib import Path

if sys.version_info[0] != 3 or sys.version_info[1] < 12:
    print(f'This script requires Python 3.12 or later: {sys.version_info[1]}', file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import BinaryIO, Literal, Optional

from git_hooks.utils import path
from git_hooks.install import list_hotl, status, install
from git_hooks.hda_filter import (
    log,
    clean, smudge
)
from git_hooks.version import __version__, IDENT

type FilterCmd = Literal['clean', 'smudge', 'configure', 'status', 'list']

def main(command: FilterCmd,
         file: Optional[str]=None,
         *,
         input: Optional[bool] = False,
         output: Optional[bool] = False,
         f_input: BinaryIO = sys.stdin.buffer,
         f_output: BinaryIO = sys.stdout.buffer,
         hotl: Optional[str] = None,
         local: bool = False,
         debug: bool = False):
    """
    Command-line interface for the HDA filter.
    """
    if debug:
        log.setLevel('DEBUG')
    # For debugging, for the clean and smudge commands, we can supply --input and/or --output,
    # to substitute files for stdin and stdout.
    # Based on the given filename, the flow is <input.hda> => <input.hda_txt> => <input_smudged.hda>
    match command:
        case 'clean':
            fpath = path(file, reason='No file specified for clean operation')
            infile, outfile = fpath, fpath.with_suffix('.hda_txt')
        case 'smudge':
            fpath = path(file, reason='No file specified for smudge operation')
            infile = fpath.with_suffix('.hda_txt')
            outfile = fpath.with_stem(fpath.stem + '_smudged')
        case _:
            infile, outfile = None, None
    if input and infile is not None:
        log.warning('Opening %s for input', infile)
        with open(infile, 'rb') as fin:
            return main(command, file, f_input=fin, f_output=f_output, output=output, debug=debug)
    elif output and outfile is not None:
        log.warning("Opening %s for output", outfile)
        with open(outfile, 'wb') as fout:
            return main(command, file, f_input=f_input, f_output=fout, input=input, debug=debug)
    match command:
        case 'install':
            install(path(file, optional=True),
                      hotl=hotl,
                      local=local)
        case 'status':
              status(local=local)
        case 'list':
            list_hotl()
        case 'clean':
            clean(path(file), f_input, f_output)
        case 'smudge':
            smudge(path(file), f_input, f_output)
        case _:
            print(f"Unknown command: {command}", file=sys.stderr)
            exit(1)

def cmdline():
    """
    Handle command-line argments and run the main function.
    """
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('--debug', '-d',
                        action='store_true',
                        help='Enable debug logging')
    subcmds = parser.add_subparsers(dest='command')
    clean_parser = subcmds.add_parser('clean',
                                      description='Turn the HDA into textual form for git storage')
    clean_parser.add_argument('--input',
                              action='store_true',
                              help='Read the file from file rather than stdin')
    clean_parser.add_argument('--output',
                              action='store_true',
                              help='write the file from file rather than stdin')
    clean_parser.add_argument('file',
                                type=Path,
                                help='The file to clean')
    smudge_parser = subcmds.add_parser('smudge',
                                       description='Turn the HDA into binary form for Houdini')
    smudge_parser.add_argument('--input',
                              action='store_true',
                              help='Read the file from file rather than stdin')
    smudge_parser.add_argument('--output',
                              action='store_true',
                              help='write the file from file rather than stdin')
    smudge_parser.add_argument('file',
                                 type=Path,
                                 help='The file to smudge')
    install_parser = subcmds.add_parser('install',
                                       description='''
                                       Install and configure this command.
                                       ''')
    install_parser.add_argument('--hotl',
                               nargs='?',
                               type=Path,
                               help='The hotl command to use')
    install_parser.add_argument('--local',
                               action='store_true',
                               help='Set the configuration locally rather than globally')
    install_parser.add_argument('file',
                               metavar='install_dir',
                               type=Path,
                               nargs='?',
                               help='Location to install this script. It should be a location on the path.')
    list_parser = subcmds.add_parser('list',
                                     description='List all Houdini installations.')
    show_parser = subcmds.add_parser('status',
                                     description='Show the current configuration.')
    args = parser.parse_args()
    main(**vars(args))

if __name__ == '__main__':
    cmdline()
