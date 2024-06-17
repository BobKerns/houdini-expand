#!/usr/bin/env python3

import sys

if sys.version_info[0] != 3 or sys.version_info[1] < 12:
    print(f'This script requires Python 3.12 or later: {sys.version_info[1]}', file=sys.stderr)
    sys.exit(1)

from typing import Literal, Optional, TypedDict
import logging
from pathlib import Path
from shutil import which, copyfile
from subprocess import run, CompletedProcess, CalledProcessError
from tempfile import NamedTemporaryFile, TemporaryDirectory
from hashlib import sha256
from io import BufferedReader, BufferedWriter
import os

import hashlib
type Hash = hashlib._Hash

logging.basicConfig(level=logging.INFO,
                    handlers=[logging.StreamHandler(sys.stderr)],
)
log = logging.getLogger(Path(__file__).stem)

CONFIG_HOTL = 'hdafilter.hotl'
SEPARATOR='--------'

type FilterCmd = Literal['clean', 'smudge', 'configure', 'show', 'list']
type Sha256Hex = str

def hash(data:str|bytes=b'') -> hash:
    if isinstance(data, str):
        data = data.encode()
    return sha256(data)

def update(hash: Hash, data: str|bytes):
    if isinstance(data, str):
        data = data.encode()
    hash.update(data)

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

type EntryType = Literal['file', 'directory', 'symlink', 'footer']
                         
class Header(TypedDict):
    """
    Header for a file or other entry.
    """
    type: EntryType
    name: str
    @classmethod
    def write(cls, header, f_output: BufferedWriter) -> str:
        """
        Return the header as a string.
        """
        keys = [f'{key}:{value}' for key, value in header.items()]
        header = f'\n{SEPARATOR}\n{'\n'.join(keys)}\n{SEPARATOR}\n'
        f_output.write(header.encode())
        # Flush before we switch to binary mode
        f_output.flush()
        return header

    @classmethod
    def read(cls, f_input: BufferedReader) -> 'Header':
        """
        Read the header from stdin.
        """
        separators: int = 2
        header = {}
        for line in f_input:
            line = line.strip()
            if separators == 0:
                break
            match line:
                case None:
                    break
                case _ if line == SEPARATOR:
                    separators -= 1
                case _ if line == '':
                    continue
                case _:
                    return cls(header)
            key, value = line.split(':', 2)
            # Do type conversions based on the declared type
            key_type = cls.__annotations__.get(key, str)
            match key_type:
                case _ if key_type == int:
                    value = int(value)
                case _ if key_type == Path:
                    value = Path(value)
                case _:
                    ...
            header[key.strip()] = value.strip()
        return cls(**header)

class FileHeader(Header):
    """
    Header for a file entry.
    """
    sha256: Sha256Hex
    length: int

class SymlinkHeader(Header):
    """
    Header for a symlink entry.
    """
    target: str

class DirectoryHeader(Header):
    """
    Header for a directory entry.
    """
    pass

class DirectoryFooter(Header):
    """
    Footer for a directory entry.
    """
    sha: Sha256Hex

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

def find_path_dir() -> Path:
    """
    Find the path directory.
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

def install(dir: Optional[Path], *,
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
        for hotl in locations():
            if hotl.is_file():
                log.info(f'Found hotl: {hotl}')
                config(CONFIG_HOTL, hotl, local=local)
    elif hotl.isfile():
        config(CONFIG_HOTL, hotl, local=local)
    else:
        log.warning('No hotl command found. Is Houdini installed?')
    toplevel = git('rev-parse', '--show-toplevel').strip()
    if toplevel is None:
        raise Exception("The current directory is not within a git working tree.")
    toplevel = Path(toplevel)
    gitattributes = toplevel / '.gitattributes'
    if dir is None or not dir.is_writeable():
        dir = find_path_dir()
    if not os.access(dir, os.W_OK):
        dir = None
    script = Path(__file__)
    if dir is not None:
        install_loc = dir / script.name
        log.info('Installing %s to %s', script, install_loc)
        copyfile(script, install_loc)
        install_loc.chmod(0o755)
    if which(script.name) is None:
        log.warning('Script not on the path. Add %s to the path.', dir)
    config('filter.hda.clean', 'hda_filter clean %f', local=local)
    config('filter.hda.smudge', 'hda_filter smudge %f', local=local)
    config('filter.hda.required', True, local=local)
    attrs = load_gitattribtes(gitattributes)
    attrs['*.hda'] = 'filter=hda dif=hda merge=hda -text lockable'
    save_gitattributes(gitattributes, attrs)
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

def load_gitattribtes(gitattributes: Path) -> dict[str, str]:
    """
    Load the .gitattributes file.
    """
    if not gitattributes.exists():
        return {}
    with gitattributes.open() as fin:
        return {line.split()[0]: line.split()[1] for line in fin}

def save_gitattributes(gitattributes: Path, attrs: dict[str, str]):
    """
    Save the .gitattributes file.
    """
    with gitattributes.open('w') as fout:
        for key, value in attrs.items():
            print(f'{key} {value}', file=fout)

def show_config():
    """
    Show the current configuration
    """
    hotl = config(CONFIG_HOTL)
    if hotl is None:
        install()
        hotl = config(CONFIG_HOTL)
    clean, smudge = get_git_lfs()
    def show(key, value):
        print(f'{key:>14}: {value}')
    show('hotl', hotl)
    show('git-lfs clean', clean)
    show('git-lfs smudge', smudge)
    show('filter.hda.clean', config('filter.hda.clean'))
    show('filter.hda.smudge', config('filter.hda.smudge'))
    show('filter.hda.required', config('filter.hda.required'))

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

def clean(file: Path, f_input: BufferedReader=sys.stdin.buffer, f_output: BufferedWriter=sys.stdout.buffer):
    """
    Clean the file using the hotl command.
    """
    hotl = get_hotl()
    clean, _ = get_git_lfs(file)
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

def encode_directory(root: Path, dir: Path, f_output: BufferedWriter=sys.stdout.buffer) -> Sha256Hex:
    """
    Encode a directory into a textual format.
    """
    dir_hdr = DirectoryHeader(type='directory', name=dir.relative_to(root))
    header = Header.write(dir_hdr, f_output)
    dirhash = hash(header)
    for f in sorted(dir.iterdir()):
        if f.is_file():
            with f.open('rb') as fin:
                data = fin.read()
                sha = hash(data).hexdigest()
                file_hdr = FileHeader(type='file', name=f.relative_to(root), sha256=sha, length=len(data))
                header = Header.write(file_hdr, f_output)
                f_output.write(data)
                f_output.write(b"\n")  # Ensure at least one newline
                update(dirhash, header)
        elif f.is_dir():
            update(dirhash, encode_directory(root, f, f_output))
        elif f.is_symlink():
            sl_header = SymlinkHeader(type='symlink', name=f.relative_to(root), target=f.resolve().relative_to(root))
            header = Header.write(sl_header, f_output)
            update(dirhash, header)
        else:
            raise ValueError(f'Unknown file type: {f}')
    dir_footer = DirectoryFooter(type='footer', sha=dirhash.hexdigest())
    footer = Header.write(dir_footer, f_output)
    update(dirhash, footer)
    return dirhash.hexdigest()
        
def read_oid(f_input: BufferedReader) -> bytes:
    """
    Read the OID from stdin.
    """
    l1 = f_input.readline()
    l2 = f_input.readline()
    l3 = f_input.readline()
    return b'\n'.join([l1, l2, l3])

def smudge_via_lfs(oid: str, file: Path,
                   f_output: BufferedWriter=sys.stdout.buffer):
    """
    Smudge the file using the git-lfs command.
    """
    _, smudge = get_git_lfs(file)
    run(smudge.split(' '),
        input=oid,
        stdout=f_output,
        check=True)
    log.debug('Smudged %s via git-lfs', file)

def smudge(file: Path,
           f_input: BufferedReader=sys.stdin.buffer,
           f_output: BufferedWriter=sys.stdout.buffer):
    """
    Smudge the file using the hotl command.
    """
    oid = read_oid(f_input)
    hotl = get_hotl()
    if hotl is None:
        # If we don't have Houdini available, we get the binary from git-lfs.
        return smudge_via_lfs(oid, file, f_output)
    else:  
        with TemporaryDirectory() as tmpdir:
            if not decode_directory(tmpdir, file, f_input):
                return smudge_via_lfs(oid, file, f_output)
            run([hotl, '-l', tmpdir, file], check=True)
        log.debug('Smudged %s from text.', file)

def decode_file(root: Path, file_header: FileHeader, f_input: BufferedReader) -> Sha256Hex:
    """
    Decode a file from a textual format.
    """
    file = root / file_header['name']
    length: int = file_header['length']
    log.debug('File: %, size=%d', file.relative_to(root), length)
    sha = hash()
    with file.open('wb') as fout:
        data = f_input.read(length)
        fout.write(data)
        sha = hash(data).hexdigest()
        if sha != file_header['sha256']:
            raise ValueError('File hash mismatch')
        return sha
    
def decode_symlink(root: Path, sl_header: SymlinkHeader) -> Sha256Hex:
    """
    Decode a symlink from a textual format.
    """
    sl = root / sl_header['name']
    target = (root / sl_header['target']).relative_to(root)
    log.debug('Symlink: %s -> %s', sl, target)
    try:
        sl.symlink_to(target)
    except FileExistsError:
        log.warning('Symlink already exists: %s', sl)
    return ''

def decode_directory(root: Path, dir_header: DirectoryHeader, f_input: BufferedReader) -> Sha256Hex:
    """
    Decode a directory from a textual format.
    """
    log.debug('Directory: %s", file.relative_to(root)}] ')
    dir_hash = hash()
    while header := Header.read(f_input):
        if header is None:
            raise ValueError('Unexpected EOF')
        match header.type:
            case 'file':
                update(dir_hash, decode_file(root, header, f_input))
            case 'symlink':
                update(dir_hash, decode_symlink(root, header))
            case 'directory':
                update(dir_hash, decode_directory(root, header, f_input))
            case 'footer':
                if dir_hash.hexdigest() != header['sha']:
                    raise ValueError('Directory hash mismatch') 
                return header['sha'] == hash().hexdigest()
            case _:
                raise ValueError(f'Unknown header: {header}')

def main(command: FilterCmd,
         file: Optional[str]=None,
         *,
         input: Optional[bool] = False,
         output: Optional[bool] = False,
         f_input: BufferedReader = sys.stdin,
         f_output: BufferedWriter = sys.stdout,
         hotl: Optional[str] = None,
         local: Optional[bool] = False,
         debug: bool = False):
    """
    Command-line interface for the HDA filter.
    """
    if debug: 
        log.setLevel('DEBUG')
    # For debugging, we can supply --input and/or --output, to substitute files for stdin and stdout.
    # Based on the given filename, the flow is <input.hda> => <input.hda_txt> => <input_smudged.hda>
    match command:
        case 'clean':
            infile, outfile = file, file.with_suffix('.hda_txt')
        case 'smudge':
            infile, outfile = file.with_suffix('.hda_txt'), file.with_stem(file.stem + '_smudged')
        case _:
            infile, outfile = None, None
    if input:
        log.warning('Opening %s for input', infile)
        with open(infile, 'rb') as fin:
            return main(command, file, f_input=fin, f_output=f_output, output=output, debug=debug)
    elif output:
        log.warning("Opening %s for output", outfile)
        with open(outfile, 'wb') as fout:
            return main(command, file, f_input=f_input, f_output=fout, input=input, debug=debug)
    match command:
        case 'install':
            install(file,
                      hotl=hotl,
                      local=local)
        case 'show':
              show_config(file, hotl=hotl, local=local)
        case 'list':
            list_hotl()
        case 'clean':
            clean(Path(file), f_input, f_output)
        case 'smudge':
            smudge(Path(file), f_input, f_output)
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
                                     description='List all Houdini installations')
    show_parser = subcmds.add_parser('show',
                                     description='Show the current hotl command')
    args = parser.parse_args()
    main(**vars(args))