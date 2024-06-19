"""
Encode the a file into a textual format.
"""

from contextlib import contextmanager
from datetime import date
from platform import python_version
from subprocess import run
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import BinaryIO, Literal, TypedDict, cast
from pathlib import Path
from hashlib import sha256
import sys
from shutil import copyfileobj

import platformdirs

from git_hooks.utils import log

import hashlib

from git_hooks.version import __version__
type Hash = hashlib._Hash

FORMAT_VERSION=1
SEPARATOR='--------'

type Sha256Hex = str

def hash(data:str|bytes=b'') -> Hash:
    """
    Allocate a new cryptographic hash object.
    If data is provided, update the hash with the data.
    It can be a string or bytes.

    :param data: The initial data to hash.
    """
    if isinstance(data, str):
        data = data.encode()
    return sha256(data)

def update(hash: Hash, data: str|bytes):
    """
    Update the hash with the data.

    :param hash: The hash object.
    :param data: The data to hash. It can be a string or bytes.
    """
    if isinstance(data, str):
        data = data.encode()
    hash.update(data)

type EntryType = Literal['metadata', 'file', 'directory', 'symlink', 'footer']

class Header(TypedDict):
    """
    Header for a file or other entry.
    """
    type: EntryType
    name: Path

class MetadataHeader(TypedDict):
    """
    Header for netadata of the archive.
    """
    format_version: int
    git_hooks_version: str
    git_hooks_commit: str
    python_version: str
    platformdirs: str
    path: Path
    date: date

def write_header(header, f_output: BinaryIO) -> str:
    """
    Return the header as a string.
    """
    keys = [f'{key}:{value}' for key, value in header.items()]
    header = f'\n{SEPARATOR}\n{'\n'.join(keys)}\n{SEPARATOR}\n'
    f_output.write(header.encode())
    # Flush before we switch to binary mode
    f_output.flush()
    return header

def read_header[T: Header](cls:type[T], f_input: BinaryIO) -> T:
    """
    Read the header from stdin.
    """
    separators: int = 2
    header: T = cast(T, {})
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
        key, value = line.split(b':', 2)
        key = key.decode().strip()
        # Do type conversions based on the declared type
        key_type = cls.__annotations__.get(key, str)
        match key_type:
            case _ if key_type == int:
                value = int(value)
            case _ if key_type == Path:
                value = Path(value.decode())
            case _:
                value = key_type(value)
        header[key] = value
    return cls(header)

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
    target: Path

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

def encode_directory(root: Path, dir: Path, f_output: BinaryIO=sys.stdout.buffer) -> Sha256Hex:
    """
    Encode a directory into a textual format.
    """
    relpath = dir.relative_to(root)
    dir_hdr = DirectoryHeader(type='directory', name=relpath)
    header = write_header(dir_hdr, f_output)
    dirhash = hash(header)
    for f in sorted(dir.iterdir()):
        if f.is_file():
            with f.open('rb') as fin:
                data = fin.read()
                sha = hash(data).hexdigest()
                file_hdr = FileHeader(type='file', name=f.relative_to(root), sha256=sha, length=len(data))
                header = write_header(file_hdr, f_output)
                f_output.write(data)
                f_output.write(b"\n")  # Ensure at least one newline
                update(dirhash, header)
        elif f.is_dir():
            update(dirhash, encode_directory(root, f, f_output))
        elif f.is_symlink():
            sl_header = SymlinkHeader(type='symlink', name=f.relative_to(root), target=f.resolve().relative_to(root))
            header = write_header(sl_header, f_output)
            update(dirhash, header)
        else:
            raise ValueError(f'Unknown file type: {f}')
    dir_footer = DirectoryFooter(type='footer', name=relpath, sha=dirhash.hexdigest())
    footer = write_header(dir_footer, f_output)
    update(dirhash, footer)
    return dirhash.hexdigest()


def decode_file(root: Path, file_header: FileHeader, f_input: BinaryIO) -> Sha256Hex:
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

def decode_directory(root: Path, dir_header: DirectoryHeader, f_input: BinaryIO) -> Sha256Hex:
    """
    Decode a directory from a textual format.
    """
    log.debug('Directory: %s", file.relative_to(root)}] ')
    dir_hash = hash()
    while header := read_header(Header, f_input):
        if header is None:
            raise ValueError('Unexpected EOF')
        match header["type"]:
            case 'file':
                file_hdr = cast(FileHeader, header)
                update(dir_hash, decode_file(root, file_hdr, f_input))
            case 'symlink':
                symlink_hdr = cast(SymlinkHeader, header)
                update(dir_hash, decode_symlink(root, symlink_hdr))
            case 'directory':
                update(dir_hash, decode_directory(root, header, f_input))
            case 'footer':
                footer = cast(DirectoryFooter, header)
                if dir_hash.hexdigest() != footer['sha']:
                    raise ValueError('Directory hash mismatch')
                digest = cast(Sha256Hex, dir_hash.hexdigest())
                if footer['sha'] != digest:
                    raise ValueError('Directory hash mismatch')
                return digest
            case _:
                raise ValueError(f'Unknown header: {header}')
    else:
        raise ValueError('Unexpected EOF')

class DecoderFailure(Exception):
    pass

@contextmanager
def encode_stream(hotl: Path, file: Path, f_input: BinaryIO, f_output: BinaryIO):
    """
    Encode a file into a textual format.
    """
    with TemporaryDirectory() as tmpdir:
        dir = Path(tmpdir)
        with NamedTemporaryFile(prefix=f'{file.stem}_',
                                suffix=file.suffix,
                                delete_on_close=False) as blob:
            copyfileobj(f_input, blob)
            yield (dir, Path(blob.name))

@contextmanager
def decode_stream(f_input: BinaryIO):
    """
    Decode a file from a textual format.
    """
    with TemporaryDirectory() as tmpdir:
        header = read_header(DirectoryHeader, f_input)
        if not decode_directory(Path(tmpdir), header, f_input):
            raise DecoderFailure(f'Failed to decode')
        yield tmpdir

def smudge_via_decode(file: Path, f_input: BinaryIO, hotl: Path) -> bool:
    with TemporaryDirectory() as tmpdir:
        header = read_header(DirectoryHeader, f_input)
        if not decode_directory(Path(tmpdir), header, f_input):
            return False
        run([hotl, '-l', tmpdir, file], check=True)
    log.debug('Smudged %s from text.', file)
    return True
