#!/usr/bin/env python3
"""
Command line interface for git_hooks.
"""

import sys
from pathlib import Path
import errno
from argparse import ArgumentParser, RawDescriptionHelpFormatter

if sys.version_info[0] != 3 or sys.version_info[1] < 12:
    print(f'This script requires Python 3.12 or later: {sys.version_info[1]}', file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import BinaryIO, Literal, Optional
import re

from git_hooks.utils import path, log
from git_hooks.git import git
from git_hooks.install import list_hotl, status, install
from git_hooks.hda_filter import (
    clean, smudge
)
from git_hooks.version import __version__, IDENT

from logging.config import fileConfig

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
         debug: bool = False,
         log_config: Optional[str] = '$GIT_DIR/info/git_hooks.ini',
         ):
    """
    Command-line interface for the HDA filter.
    """
    if log_config:
        git_dir = Path(git('rev-parse', '--git-dir').strip())
        log_config = log_config.replace('$GIT_DIR', str(git_dir))
        log_config = log_config.replace('$HOME', str(Path.home()))
        if log_config.startswith('~'):
            log_config = str(Path.home()) + log_config[1:]
        if log_config != '':
            log_config_file = Path(log_config)
            if log_config_file.is_file():
                fileConfig(log_config_file)
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
        log.info('Opening %s for input', infile)
        with open(infile, 'rb') as fin:
            return main(command, file, f_input=fin, f_output=f_output, output=output, debug=debug)
    elif output and outfile is not None:
        log.info("Opening %s for output", outfile)
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

re_trim = re.compile(r'(?:^\n\s*$)+|(:?^\n\s*$)')
re_ws_start = re.compile(r'^\s+')
def trim(msg: str, indent: int=0) -> str:
    """
    Clean the message for printing.

    Removes blank lines from beginning and end, then
    removes the initial indentation from all lines,
    and replaces it with the given number of spaces.

    The initial indentation is the minimum number of spaces
    on any non-blank line.
    """
    msg = re_trim.sub('', msg)
    if indent >= 0:
        lines = msg.split('\n')
        min_indent = min(
            len(line) - len(line.lstrip())
            for line in lines
            if line.strip())
        re_prefix = re.compile(r'^\s{%d}' % min_indent)
        msg = '\n'.join(re_prefix.sub(' ' * indent, line) for line in lines)
        msg = re_ws_start.sub(' ' * indent, msg)
    return msg

def cmdline():
    """
    Handle command-line argments and run the main function.
    """
    parser = ArgumentParser(
        description=trim(f'''
        Git filter for various binary file types:
        .hda, .tar, .tar.gz, .tar.bz2, .tar.xz, .tar.zst
        ''',
        indent=2),
        epilog=trim(f'''
        Version: {__version__}
        Commit: {IDENT}
        '''),
        formatter_class=RawDescriptionHelpFormatter,
    )
    parser.add_argument('--debug', '-d',
                        action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--log-config',
                        type=Path,
                        help='The logging configuration file, defaults to $GIT_DIR/info/git_hooks.ini')
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
    try:
        main(**vars(args))
    except BrokenPipeError:
        exit(errno.EPIPE)

if __name__ == '__main__':
    cmdline()
