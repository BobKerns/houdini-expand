"""
Tools for managing git attributes.
"""

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Optional


class AttributeState(Enum):
    """
    The state of a git attribute.
    """
    UNSET = auto()
    SET = auto()
    UNSPECIFIED = auto()

@dataclass
class GitAttribute:
    """
    A git attribute.
    """
    name: str
    value: str|AttributeState

    @classmethod
    def parse(cls, item: str) -> 'GitAttribute':
        """
        Parse a git attribute.
        """
        match item:
            case _ if item.startswith('-'):
                return cls(item[1:], AttributeState.UNSET)
            case _ if '=' in item:
                name, value = item.split('=', 2)
                return cls(name, value)
            case _:
                return cls(item, AttributeState.SET)

    def __str__(self) -> str:
        """
        Return the attribute as a string.
        """
        match self.value:
            case AttributeState.UNSET:
                return f'-{self.name}'
            case AttributeState.SET:
                return self.name
            case _:
                return f'{self.name}={self.value}'

class GitAttributeSet:
    """
    A set of git attributes.
    """
    attributes: dict[str, GitAttribute]
    def __init__(self, **attrs):
        self.attributes = attrs

    def get(self, key: str) -> GitAttribute:
        """
        Get an attribute.
        """
        attr =  self.attributes.get(key, None)
        return attr or GitAttribute(key, AttributeState.UNSPECIFIED)

    def set_attributes(self, *tokens: str, **kwargs: str):
        """
        Set the attributes in a convenient way.

        PARAMS:
        tokens: The attribute tokens to set. These can be in the form of '-text' to unset an attribute,
                'text' to set an attribute, or 'filter.hda' to set an attribute with a value.
        kwargs: Additional attributes to set. These can be in the form of filter='hda' to set an attribute with a value.

        EXAMPLE:
        attribs = GitAttributeFile('.gitattributes')
        attribs['*.hda'].set_attributes('-text', 'lockable', filter='hda', diff='hda', merge='hda')
        """
        for token in tokens:
            attr = GitAttribute.parse(token)
            self.attributes[attr.name] = attr
        for name, value in kwargs.items():
            self.attributes[name] = GitAttribute(name, value)

    def parse_and_set(self, line: str):
        """
        Parse and set the attributes.
        """
        for attr in GitAttributeSet.parse(line):
            self[attr.name] = attr

    def set(self, key: str, value: str|AttributeState):
        """
        Set an attribute.
        """
        self.attributes[key] = GitAttribute(key, value)

    def unset(self, key: str):
        """
        Unset an attribute.

        PARAMS:
        key: The attribute key.
        """
        self.attributes[key] = GitAttribute(key, AttributeState.UNSET)

    def __getitem__(self, key: str) -> GitAttribute:
        """
        Get an attribute.

        PARAMS:
        key: The attribute key.
        """
        return self.get(key)

    def __setitem__(self, key: str, value: str|AttributeState|GitAttribute):
        """
        Set an attribute.

        PARAMS:
        key: The attribute key.
        value: The attribute value. This can be a string, an AttributeState, or a GitAttribute.
        """
        match value:
            case GitAttribute():
                self.attributes[key] = value
            case str()|AttributeState():
                self.attributes[key] = GitAttribute(key, value)

    def __delitem__(self, key: str):
        """
        Unset an attribute.
        """
        self.unset(key)

    def __iter__(self):
        """
        Iterate over the attributes.
        """
        return iter(self.attributes.values())

    def __len__(self):
        """
        Return the number of attributes.
        """
        return len(self.attributes)

    def __str__(self):
        """
        Return the attributes as a string.
        """
        return ' '.join(str(attr) for attr in self.attributes.values())

    def __repr__(self):
        """
        Return the attributes as a string.
        """
        return str(self)

    def __contains__(self, key: str):
        """
        Check if an attribute is set.
        """
        return key in self.attributes

    def __bool__(self):
        """
        Check if there are any attributes.
        """
        return bool(self.attributes)
    @classmethod
    def parse(cls, line: str) -> 'GitAttributeSet':
        """
        Parse a git attribute set.
        """
        attrs = {
            attr.name: attr
            for item in line.split()
            for attr in (GitAttribute.parse(item),)
            }
        return cls(**attrs)

class GitAttributesFile:
    """
    A .gitattributes file.
    """
    file: Path
    attributes: dict[str, GitAttributeSet]

    def __init__(self, file: Path, attrs: Optional[dict[str, GitAttributeSet]]=None):
        self.file = file
        self.attributes = attrs or {}

    def __getitem__(self, key: str) -> GitAttributeSet:
        """
        Get the attributes for a file.
        """
        attrset =self.attributes.get(key, None)
        if attrset is None:
            attrset = GitAttributeSet()
            self.attributes[key] = attrset
        return attrset

    def __setitem__(self, key: str, value: GitAttributeSet):
        """
        Set the attributes for a file.
        """
        self.attributes[key] = value

    def __delitem__(self, key: str):
        """
        Delete the attributes for a file.
        """
        del self.attributes[key]

    def __contains__(self, key: str):
        """
        Check if the attributes are set for a file.
        """
        return key in self.attributes and self.attributes[key]

    def __iter__(self):
        """
        Iterate over the files.
        """
        return iter(self.attributes.items())

    def __len__(self):
        """
        Return the number of files.
        """
        return len(self.attributes)

    @classmethod
    def load(cls, gitattributes: Path) -> 'GitAttributesFile':
        """
        Load the .gitattributes file.
        """
        if not gitattributes.exists():
            return GitAttributesFile(gitattributes)
        with gitattributes.open() as fin:
            attrs = {
                split[0]: GitAttributeSet.parse(split[1])
                for line in fin
                for split in (line.split(' ', 1),)
                if len(split) == 2
            }
            return GitAttributesFile(gitattributes, attrs)

    def save(self, gitattributes: Optional[Path]=None):
        """
        Save the .gitattributes file.
        """
        gitattributes = gitattributes or self.file
        with gitattributes.open('w') as fout:
            for key, value in self.attributes.items():
                if len(value) > 0:
                    print(f'{key} {value}', file=fout)
