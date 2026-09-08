"""Generated typed nodes; edit the schema or generator, not this file."""
from __future__ import annotations

from pydantree_sitter import Grammar, Node
from pydantree_sitter.nodes import NodeMeta
from pydantree_sitter.schema import NodeSchema

__schema__ = NodeSchema.from_list([{'extra': False,
  'named': True,
  'root': False,
  'subtypes': [{'named': True, 'type': 'false'},
               {'named': True, 'type': 'number'},
               {'named': True, 'type': 'string'},
               {'named': True, 'type': 'true'}],
  'type': 'value'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'value'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'array'},
 {'extra': False,
  'fields': {'key': {'multiple': False,
                     'required': True,
                     'types': [{'named': True, 'type': 'string'}]},
             'value': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': 'value'}]}},
  'named': True,
  'root': False,
  'type': 'pair'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'array'},
                         {'named': True, 'type': 'pair'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': True,
  'type': 'source_file'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'escape_sequence'},
                         {'named': True, 'type': 'string_content'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'string'},
 {'extra': False, 'named': False, 'root': False, 'type': '"'},
 {'extra': False, 'named': False, 'root': False, 'type': ','},
 {'extra': False, 'named': False, 'root': False, 'type': ':'},
 {'extra': False, 'named': False, 'root': False, 'type': '['},
 {'extra': False, 'named': False, 'root': False, 'type': ']'},
 {'extra': False, 'named': True, 'root': False, 'type': 'escape_sequence'},
 {'extra': False, 'named': True, 'root': False, 'type': 'false'},
 {'extra': False, 'named': True, 'root': False, 'type': 'number'},
 {'extra': False, 'named': True, 'root': False, 'type': 'string_content'},
 {'extra': False, 'named': True, 'root': False, 'type': 'true'}])
__fingerprint__ = ()

class Array(Node):
    __kind__ = 'array'
    __schema__ = None
    content: list[Value]

class Pair(Node):
    __kind__ = 'pair'
    __schema__ = None
    key: String
    value: Value

class SourceFile(Node):
    __kind__ = 'source_file'
    __schema__ = None
    content: list[Array | Pair]

class String(Node):
    __kind__ = 'string'
    __schema__ = None
    content: list[EscapeSequence | StringContent]

class EscapeSequence(Node):
    __kind__ = 'escape_sequence'
    __schema__ = None

class False_(Node):
    __kind__ = 'false'
    __schema__ = None

class Number(Node):
    __kind__ = 'number'
    __schema__ = None

class StringContent(Node):
    __kind__ = 'string_content'
    __schema__ = None

class True_(Node):
    __kind__ = 'true'
    __schema__ = None

Value = False_ | Number | String | True_

KIND_MAP = {
    'array': Array,
    'pair': Pair,
    'source_file': SourceFile,
    'string': String,
    'escape_sequence': EscapeSequence,
    'false': False_,
    'number': Number,
    'string_content': StringContent,
    'true': True_,
}

for _node_class in KIND_MAP.values():
    _node_class.__schema__ = __schema__
    NodeMeta.rebuild(_node_class, globals())

grammar = Grammar._from_generated(__name__, '', __fingerprint__)
