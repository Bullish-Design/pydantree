"""Generated typed nodes; edit the schema or generator, not this file."""
from __future__ import annotations

from typing import Literal as _Literal

from pydantree_sitter import Grammar, Node
from pydantree_sitter.nodes import NodeMeta
from pydantree_sitter.schema import NodeSchema

__schema__ = NodeSchema.from_list([{'extra': False,
  'named': True,
  'root': False,
  'subtypes': [{'named': True, 'type': 'apply_expression'},
               {'named': True, 'type': 'assert_expression'},
               {'named': True, 'type': 'attrset_expression'},
               {'named': True, 'type': 'binary_expression'},
               {'named': True, 'type': 'float_expression'},
               {'named': True, 'type': 'function_expression'},
               {'named': True, 'type': 'has_attr_expression'},
               {'named': True, 'type': 'hpath_expression'},
               {'named': True, 'type': 'if_expression'},
               {'named': True, 'type': 'indented_string_expression'},
               {'named': True, 'type': 'integer_expression'},
               {'named': True, 'type': 'let_attrset_expression'},
               {'named': True, 'type': 'let_expression'},
               {'named': True, 'type': 'list_expression'},
               {'named': True, 'type': 'parenthesized_expression'},
               {'named': True, 'type': 'path_expression'},
               {'named': True, 'type': 'rec_attrset_expression'},
               {'named': True, 'type': 'select_expression'},
               {'named': True, 'type': 'spath_expression'},
               {'named': True, 'type': 'string_expression'},
               {'named': True, 'type': 'unary_expression'},
               {'named': True, 'type': 'uri_expression'},
               {'named': True, 'type': 'variable_expression'},
               {'named': True, 'type': 'with_expression'}],
  'type': '_expression'},
 {'extra': False,
  'fields': {'argument': {'multiple': False,
                          'required': True,
                          'types': [{'named': True, 'type': 'attrset_expression'},
                                    {'named': True, 'type': 'float_expression'},
                                    {'named': True, 'type': 'hpath_expression'},
                                    {'named': True,
                                     'type': 'indented_string_expression'},
                                    {'named': True, 'type': 'integer_expression'},
                                    {'named': True, 'type': 'let_attrset_expression'},
                                    {'named': True, 'type': 'list_expression'},
                                    {'named': True, 'type': 'parenthesized_expression'},
                                    {'named': True, 'type': 'path_expression'},
                                    {'named': True, 'type': 'rec_attrset_expression'},
                                    {'named': True, 'type': 'select_expression'},
                                    {'named': True, 'type': 'spath_expression'},
                                    {'named': True, 'type': 'string_expression'},
                                    {'named': True, 'type': 'uri_expression'},
                                    {'named': True, 'type': 'variable_expression'}]},
             'function': {'multiple': False,
                          'required': True,
                          'types': [{'named': True, 'type': 'apply_expression'},
                                    {'named': True, 'type': 'attrset_expression'},
                                    {'named': True, 'type': 'float_expression'},
                                    {'named': True, 'type': 'hpath_expression'},
                                    {'named': True,
                                     'type': 'indented_string_expression'},
                                    {'named': True, 'type': 'integer_expression'},
                                    {'named': True, 'type': 'let_attrset_expression'},
                                    {'named': True, 'type': 'list_expression'},
                                    {'named': True, 'type': 'parenthesized_expression'},
                                    {'named': True, 'type': 'path_expression'},
                                    {'named': True, 'type': 'rec_attrset_expression'},
                                    {'named': True, 'type': 'select_expression'},
                                    {'named': True, 'type': 'spath_expression'},
                                    {'named': True, 'type': 'string_expression'},
                                    {'named': True, 'type': 'uri_expression'},
                                    {'named': True, 'type': 'variable_expression'}]}},
  'named': True,
  'root': False,
  'type': 'apply_expression'},
 {'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'apply_expression'},
                                {'named': True, 'type': 'assert_expression'},
                                {'named': True, 'type': 'attrset_expression'},
                                {'named': True, 'type': 'binary_expression'},
                                {'named': True, 'type': 'float_expression'},
                                {'named': True, 'type': 'function_expression'},
                                {'named': True, 'type': 'has_attr_expression'},
                                {'named': True, 'type': 'hpath_expression'},
                                {'named': True, 'type': 'if_expression'},
                                {'named': True, 'type': 'indented_string_expression'},
                                {'named': True, 'type': 'integer_expression'},
                                {'named': True, 'type': 'let_attrset_expression'},
                                {'named': True, 'type': 'let_expression'},
                                {'named': True, 'type': 'list_expression'},
                                {'named': True, 'type': 'parenthesized_expression'},
                                {'named': True, 'type': 'path_expression'},
                                {'named': True, 'type': 'rec_attrset_expression'},
                                {'named': True, 'type': 'select_expression'},
                                {'named': True, 'type': 'spath_expression'},
                                {'named': True, 'type': 'string_expression'},
                                {'named': True, 'type': 'unary_expression'},
                                {'named': True, 'type': 'uri_expression'},
                                {'named': True, 'type': 'variable_expression'},
                                {'named': True, 'type': 'with_expression'}]},
             'condition': {'multiple': False,
                           'required': True,
                           'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'assert_expression'},
 {'extra': False,
  'fields': {'attr': {'multiple': True,
                      'required': True,
                      'types': [{'named': True, 'type': 'identifier'},
                                {'named': True, 'type': 'interpolation'},
                                {'named': True, 'type': 'string_expression'}]}},
  'named': True,
  'root': False,
  'type': 'attrpath'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'binding_set'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'attrset_expression'},
 {'extra': False,
  'fields': {'left': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'apply_expression'},
                                {'named': True, 'type': 'attrset_expression'},
                                {'named': True, 'type': 'binary_expression'},
                                {'named': True, 'type': 'float_expression'},
                                {'named': True, 'type': 'has_attr_expression'},
                                {'named': True, 'type': 'hpath_expression'},
                                {'named': True, 'type': 'indented_string_expression'},
                                {'named': True, 'type': 'integer_expression'},
                                {'named': True, 'type': 'let_attrset_expression'},
                                {'named': True, 'type': 'list_expression'},
                                {'named': True, 'type': 'parenthesized_expression'},
                                {'named': True, 'type': 'path_expression'},
                                {'named': True, 'type': 'rec_attrset_expression'},
                                {'named': True, 'type': 'select_expression'},
                                {'named': True, 'type': 'spath_expression'},
                                {'named': True, 'type': 'string_expression'},
                                {'named': True, 'type': 'unary_expression'},
                                {'named': True, 'type': 'uri_expression'},
                                {'named': True, 'type': 'variable_expression'}]},
             'operator': {'multiple': False,
                          'required': True,
                          'types': [{'named': False, 'type': '!='},
                                    {'named': False, 'type': '&&'},
                                    {'named': False, 'type': '*'},
                                    {'named': False, 'type': '+'},
                                    {'named': False, 'type': '++'},
                                    {'named': False, 'type': '-'},
                                    {'named': False, 'type': '->'},
                                    {'named': False, 'type': '/'},
                                    {'named': False, 'type': '//'},
                                    {'named': False, 'type': '<'},
                                    {'named': False, 'type': '<='},
                                    {'named': False, 'type': '=='},
                                    {'named': False, 'type': '>'},
                                    {'named': False, 'type': '>='},
                                    {'named': False, 'type': '||'}]},
             'right': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': 'apply_expression'},
                                 {'named': True, 'type': 'attrset_expression'},
                                 {'named': True, 'type': 'binary_expression'},
                                 {'named': True, 'type': 'float_expression'},
                                 {'named': True, 'type': 'has_attr_expression'},
                                 {'named': True, 'type': 'hpath_expression'},
                                 {'named': True, 'type': 'indented_string_expression'},
                                 {'named': True, 'type': 'integer_expression'},
                                 {'named': True, 'type': 'let_attrset_expression'},
                                 {'named': True, 'type': 'list_expression'},
                                 {'named': True, 'type': 'parenthesized_expression'},
                                 {'named': True, 'type': 'path_expression'},
                                 {'named': True, 'type': 'rec_attrset_expression'},
                                 {'named': True, 'type': 'select_expression'},
                                 {'named': True, 'type': 'spath_expression'},
                                 {'named': True, 'type': 'string_expression'},
                                 {'named': True, 'type': 'unary_expression'},
                                 {'named': True, 'type': 'uri_expression'},
                                 {'named': True, 'type': 'variable_expression'}]}},
  'named': True,
  'root': False,
  'type': 'binary_expression'},
 {'extra': False,
  'fields': {'attrpath': {'multiple': False,
                          'required': True,
                          'types': [{'named': True, 'type': 'attrpath'}]},
             'expression': {'multiple': False,
                            'required': True,
                            'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'binding'},
 {'extra': False,
  'fields': {'binding': {'multiple': True,
                         'required': True,
                         'types': [{'named': True, 'type': 'binding'},
                                   {'named': True, 'type': 'inherit'},
                                   {'named': True, 'type': 'inherit_from'}]}},
  'named': True,
  'root': False,
  'type': 'binding_set'},
 {'extra': False,
  'fields': {'default': {'multiple': False,
                         'required': False,
                         'types': [{'named': True, 'type': '_expression'}]},
             'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'identifier'}]}},
  'named': True,
  'root': False,
  'type': 'formal'},
 {'extra': False,
  'fields': {'ellipses': {'multiple': False,
                          'required': False,
                          'types': [{'named': True, 'type': 'ellipses'}]},
             'formal': {'multiple': True,
                        'required': False,
                        'types': [{'named': True, 'type': 'formal'}]}},
  'named': True,
  'root': False,
  'type': 'formals'},
 {'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'apply_expression'},
                                {'named': True, 'type': 'assert_expression'},
                                {'named': True, 'type': 'attrset_expression'},
                                {'named': True, 'type': 'binary_expression'},
                                {'named': True, 'type': 'float_expression'},
                                {'named': True, 'type': 'function_expression'},
                                {'named': True, 'type': 'has_attr_expression'},
                                {'named': True, 'type': 'hpath_expression'},
                                {'named': True, 'type': 'if_expression'},
                                {'named': True, 'type': 'indented_string_expression'},
                                {'named': True, 'type': 'integer_expression'},
                                {'named': True, 'type': 'let_attrset_expression'},
                                {'named': True, 'type': 'let_expression'},
                                {'named': True, 'type': 'list_expression'},
                                {'named': True, 'type': 'parenthesized_expression'},
                                {'named': True, 'type': 'path_expression'},
                                {'named': True, 'type': 'rec_attrset_expression'},
                                {'named': True, 'type': 'select_expression'},
                                {'named': True, 'type': 'spath_expression'},
                                {'named': True, 'type': 'string_expression'},
                                {'named': True, 'type': 'unary_expression'},
                                {'named': True, 'type': 'uri_expression'},
                                {'named': True, 'type': 'variable_expression'},
                                {'named': True, 'type': 'with_expression'}]},
             'formals': {'multiple': False,
                         'required': False,
                         'types': [{'named': True, 'type': 'formals'}]},
             'universal': {'multiple': False,
                           'required': False,
                           'types': [{'named': True, 'type': 'identifier'}]}},
  'named': True,
  'root': False,
  'type': 'function_expression'},
 {'extra': False,
  'fields': {'attrpath': {'multiple': False,
                          'required': True,
                          'types': [{'named': True, 'type': 'attrpath'}]},
             'expression': {'multiple': False,
                            'required': True,
                            'types': [{'named': True, 'type': 'apply_expression'},
                                      {'named': True, 'type': 'attrset_expression'},
                                      {'named': True, 'type': 'binary_expression'},
                                      {'named': True, 'type': 'float_expression'},
                                      {'named': True, 'type': 'has_attr_expression'},
                                      {'named': True, 'type': 'hpath_expression'},
                                      {'named': True,
                                       'type': 'indented_string_expression'},
                                      {'named': True, 'type': 'integer_expression'},
                                      {'named': True, 'type': 'let_attrset_expression'},
                                      {'named': True, 'type': 'list_expression'},
                                      {'named': True,
                                       'type': 'parenthesized_expression'},
                                      {'named': True, 'type': 'path_expression'},
                                      {'named': True, 'type': 'rec_attrset_expression'},
                                      {'named': True, 'type': 'select_expression'},
                                      {'named': True, 'type': 'spath_expression'},
                                      {'named': True, 'type': 'string_expression'},
                                      {'named': True, 'type': 'unary_expression'},
                                      {'named': True, 'type': 'uri_expression'},
                                      {'named': True, 'type': 'variable_expression'}]},
             'operator': {'multiple': False,
                          'required': True,
                          'types': [{'named': False, 'type': '?'}]}},
  'named': True,
  'root': False,
  'type': 'has_attr_expression'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'interpolation'},
                         {'named': True, 'type': 'path_fragment'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'hpath_expression'},
 {'extra': False,
  'fields': {'alternative': {'multiple': False,
                             'required': True,
                             'types': [{'named': True, 'type': '_expression'}]},
             'condition': {'multiple': False,
                           'required': True,
                           'types': [{'named': True, 'type': '_expression'}]},
             'consequence': {'multiple': False,
                             'required': True,
                             'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'if_expression'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'dollar_escape'},
                         {'named': True, 'type': 'escape_sequence'},
                         {'named': True, 'type': 'interpolation'},
                         {'named': True, 'type': 'string_fragment'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'indented_string_expression'},
 {'extra': False,
  'fields': {'attrs': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': 'inherited_attrs'}]}},
  'named': True,
  'root': False,
  'type': 'inherit'},
 {'extra': False,
  'fields': {'attrs': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': 'inherited_attrs'}]},
             'expression': {'multiple': False,
                            'required': True,
                            'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'inherit_from'},
 {'extra': False,
  'fields': {'attr': {'multiple': True,
                      'required': True,
                      'types': [{'named': True, 'type': 'identifier'},
                                {'named': True, 'type': 'interpolation'},
                                {'named': True, 'type': 'string_expression'}]}},
  'named': True,
  'root': False,
  'type': 'inherited_attrs'},
 {'extra': False,
  'fields': {'expression': {'multiple': False,
                            'required': True,
                            'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'interpolation'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'binding_set'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'let_attrset_expression'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'binding_set'}]},
  'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'apply_expression'},
                                {'named': True, 'type': 'assert_expression'},
                                {'named': True, 'type': 'attrset_expression'},
                                {'named': True, 'type': 'binary_expression'},
                                {'named': True, 'type': 'float_expression'},
                                {'named': True, 'type': 'function_expression'},
                                {'named': True, 'type': 'has_attr_expression'},
                                {'named': True, 'type': 'hpath_expression'},
                                {'named': True, 'type': 'if_expression'},
                                {'named': True, 'type': 'indented_string_expression'},
                                {'named': True, 'type': 'integer_expression'},
                                {'named': True, 'type': 'let_attrset_expression'},
                                {'named': True, 'type': 'let_expression'},
                                {'named': True, 'type': 'list_expression'},
                                {'named': True, 'type': 'parenthesized_expression'},
                                {'named': True, 'type': 'path_expression'},
                                {'named': True, 'type': 'rec_attrset_expression'},
                                {'named': True, 'type': 'select_expression'},
                                {'named': True, 'type': 'spath_expression'},
                                {'named': True, 'type': 'string_expression'},
                                {'named': True, 'type': 'unary_expression'},
                                {'named': True, 'type': 'uri_expression'},
                                {'named': True, 'type': 'variable_expression'},
                                {'named': True, 'type': 'with_expression'}]}},
  'named': True,
  'root': False,
  'type': 'let_expression'},
 {'extra': False,
  'fields': {'element': {'multiple': True,
                         'required': False,
                         'types': [{'named': True, 'type': 'attrset_expression'},
                                   {'named': True, 'type': 'float_expression'},
                                   {'named': True, 'type': 'hpath_expression'},
                                   {'named': True,
                                    'type': 'indented_string_expression'},
                                   {'named': True, 'type': 'integer_expression'},
                                   {'named': True, 'type': 'let_attrset_expression'},
                                   {'named': True, 'type': 'list_expression'},
                                   {'named': True, 'type': 'parenthesized_expression'},
                                   {'named': True, 'type': 'path_expression'},
                                   {'named': True, 'type': 'rec_attrset_expression'},
                                   {'named': True, 'type': 'select_expression'},
                                   {'named': True, 'type': 'spath_expression'},
                                   {'named': True, 'type': 'string_expression'},
                                   {'named': True, 'type': 'uri_expression'},
                                   {'named': True, 'type': 'variable_expression'}]}},
  'named': True,
  'root': False,
  'type': 'list_expression'},
 {'extra': False,
  'fields': {'expression': {'multiple': False,
                            'required': True,
                            'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'parenthesized_expression'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'interpolation'},
                         {'named': True, 'type': 'path_fragment'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'path_expression'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'binding_set'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'rec_attrset_expression'},
 {'extra': False,
  'fields': {'attrpath': {'multiple': False,
                          'required': True,
                          'types': [{'named': True, 'type': 'attrpath'}]},
             'default': {'multiple': False,
                         'required': False,
                         'types': [{'named': True, 'type': 'attrset_expression'},
                                   {'named': True, 'type': 'float_expression'},
                                   {'named': True, 'type': 'hpath_expression'},
                                   {'named': True,
                                    'type': 'indented_string_expression'},
                                   {'named': True, 'type': 'integer_expression'},
                                   {'named': True, 'type': 'let_attrset_expression'},
                                   {'named': True, 'type': 'list_expression'},
                                   {'named': True, 'type': 'parenthesized_expression'},
                                   {'named': True, 'type': 'path_expression'},
                                   {'named': True, 'type': 'rec_attrset_expression'},
                                   {'named': True, 'type': 'select_expression'},
                                   {'named': True, 'type': 'spath_expression'},
                                   {'named': True, 'type': 'string_expression'},
                                   {'named': True, 'type': 'uri_expression'},
                                   {'named': True, 'type': 'variable_expression'}]},
             'expression': {'multiple': False,
                            'required': True,
                            'types': [{'named': True, 'type': 'attrset_expression'},
                                      {'named': True, 'type': 'float_expression'},
                                      {'named': True, 'type': 'hpath_expression'},
                                      {'named': True,
                                       'type': 'indented_string_expression'},
                                      {'named': True, 'type': 'integer_expression'},
                                      {'named': True, 'type': 'let_attrset_expression'},
                                      {'named': True, 'type': 'list_expression'},
                                      {'named': True,
                                       'type': 'parenthesized_expression'},
                                      {'named': True, 'type': 'path_expression'},
                                      {'named': True, 'type': 'rec_attrset_expression'},
                                      {'named': True, 'type': 'spath_expression'},
                                      {'named': True, 'type': 'string_expression'},
                                      {'named': True, 'type': 'uri_expression'},
                                      {'named': True, 'type': 'variable_expression'}]}},
  'named': True,
  'root': False,
  'type': 'select_expression'},
 {'extra': False,
  'fields': {'expression': {'multiple': False,
                            'required': False,
                            'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': True,
  'type': 'source_code'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'dollar_escape'},
                         {'named': True, 'type': 'escape_sequence'},
                         {'named': True, 'type': 'interpolation'},
                         {'named': True, 'type': 'string_fragment'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'string_expression'},
 {'extra': False,
  'fields': {'argument': {'multiple': False,
                          'required': True,
                          'types': [{'named': True, 'type': 'apply_expression'},
                                    {'named': True, 'type': 'attrset_expression'},
                                    {'named': True, 'type': 'binary_expression'},
                                    {'named': True, 'type': 'float_expression'},
                                    {'named': True, 'type': 'has_attr_expression'},
                                    {'named': True, 'type': 'hpath_expression'},
                                    {'named': True,
                                     'type': 'indented_string_expression'},
                                    {'named': True, 'type': 'integer_expression'},
                                    {'named': True, 'type': 'let_attrset_expression'},
                                    {'named': True, 'type': 'list_expression'},
                                    {'named': True, 'type': 'parenthesized_expression'},
                                    {'named': True, 'type': 'path_expression'},
                                    {'named': True, 'type': 'rec_attrset_expression'},
                                    {'named': True, 'type': 'select_expression'},
                                    {'named': True, 'type': 'spath_expression'},
                                    {'named': True, 'type': 'string_expression'},
                                    {'named': True, 'type': 'unary_expression'},
                                    {'named': True, 'type': 'uri_expression'},
                                    {'named': True, 'type': 'variable_expression'}]},
             'operator': {'multiple': False,
                          'required': True,
                          'types': [{'named': False, 'type': '!'},
                                    {'named': False, 'type': '-'}]}},
  'named': True,
  'root': False,
  'type': 'unary_expression'},
 {'extra': False,
  'fields': {'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'identifier'}]}},
  'named': True,
  'root': False,
  'type': 'variable_expression'},
 {'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'apply_expression'},
                                {'named': True, 'type': 'assert_expression'},
                                {'named': True, 'type': 'attrset_expression'},
                                {'named': True, 'type': 'binary_expression'},
                                {'named': True, 'type': 'float_expression'},
                                {'named': True, 'type': 'function_expression'},
                                {'named': True, 'type': 'has_attr_expression'},
                                {'named': True, 'type': 'hpath_expression'},
                                {'named': True, 'type': 'if_expression'},
                                {'named': True, 'type': 'indented_string_expression'},
                                {'named': True, 'type': 'integer_expression'},
                                {'named': True, 'type': 'let_attrset_expression'},
                                {'named': True, 'type': 'let_expression'},
                                {'named': True, 'type': 'list_expression'},
                                {'named': True, 'type': 'parenthesized_expression'},
                                {'named': True, 'type': 'path_expression'},
                                {'named': True, 'type': 'rec_attrset_expression'},
                                {'named': True, 'type': 'select_expression'},
                                {'named': True, 'type': 'spath_expression'},
                                {'named': True, 'type': 'string_expression'},
                                {'named': True, 'type': 'unary_expression'},
                                {'named': True, 'type': 'uri_expression'},
                                {'named': True, 'type': 'variable_expression'},
                                {'named': True, 'type': 'with_expression'}]},
             'environment': {'multiple': False,
                             'required': True,
                             'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'with_expression'},
 {'extra': False, 'named': False, 'root': False, 'type': '!'},
 {'extra': False, 'named': False, 'root': False, 'type': '!='},
 {'extra': False, 'named': False, 'root': False, 'type': '"'},
 {'extra': False, 'named': False, 'root': False, 'type': '${'},
 {'extra': False, 'named': False, 'root': False, 'type': '&&'},
 {'extra': False, 'named': False, 'root': False, 'type': "''"},
 {'extra': False, 'named': False, 'root': False, 'type': '('},
 {'extra': False, 'named': False, 'root': False, 'type': ')'},
 {'extra': False, 'named': False, 'root': False, 'type': '*'},
 {'extra': False, 'named': False, 'root': False, 'type': '+'},
 {'extra': False, 'named': False, 'root': False, 'type': '++'},
 {'extra': False, 'named': False, 'root': False, 'type': ','},
 {'extra': False, 'named': False, 'root': False, 'type': '-'},
 {'extra': False, 'named': False, 'root': False, 'type': '->'},
 {'extra': False, 'named': False, 'root': False, 'type': '.'},
 {'extra': False, 'named': False, 'root': False, 'type': '/'},
 {'extra': False, 'named': False, 'root': False, 'type': '//'},
 {'extra': False, 'named': False, 'root': False, 'type': ':'},
 {'extra': False, 'named': False, 'root': False, 'type': ';'},
 {'extra': False, 'named': False, 'root': False, 'type': '<'},
 {'extra': False, 'named': False, 'root': False, 'type': '<='},
 {'extra': False, 'named': False, 'root': False, 'type': '='},
 {'extra': False, 'named': False, 'root': False, 'type': '=='},
 {'extra': False, 'named': False, 'root': False, 'type': '>'},
 {'extra': False, 'named': False, 'root': False, 'type': '>='},
 {'extra': False, 'named': False, 'root': False, 'type': '?'},
 {'extra': False, 'named': False, 'root': False, 'type': '@'},
 {'extra': False, 'named': False, 'root': False, 'type': '['},
 {'extra': False, 'named': False, 'root': False, 'type': ']'},
 {'extra': False, 'named': False, 'root': False, 'type': 'assert'},
 {'extra': True, 'named': True, 'root': False, 'type': 'comment'},
 {'extra': False, 'named': True, 'root': False, 'type': 'dollar_escape'},
 {'extra': False, 'named': True, 'root': False, 'type': 'ellipses'},
 {'extra': False, 'named': False, 'root': False, 'type': 'else'},
 {'extra': False, 'named': True, 'root': False, 'type': 'escape_sequence'},
 {'extra': False, 'named': True, 'root': False, 'type': 'float_expression'},
 {'extra': False, 'named': True, 'root': False, 'type': 'identifier'},
 {'extra': False, 'named': False, 'root': False, 'type': 'if'},
 {'extra': False, 'named': False, 'root': False, 'type': 'in'},
 {'extra': False, 'named': False, 'root': False, 'type': 'inherit'},
 {'extra': False, 'named': True, 'root': False, 'type': 'integer_expression'},
 {'extra': False, 'named': False, 'root': False, 'type': 'let'},
 {'extra': False, 'named': False, 'root': False, 'type': 'or'},
 {'extra': False, 'named': True, 'root': False, 'type': 'path_fragment'},
 {'extra': False, 'named': False, 'root': False, 'type': 'rec'},
 {'extra': False, 'named': True, 'root': False, 'type': 'spath_expression'},
 {'extra': False, 'named': True, 'root': False, 'type': 'string_fragment'},
 {'extra': False, 'named': False, 'root': False, 'type': 'then'},
 {'extra': False, 'named': True, 'root': False, 'type': 'uri_expression'},
 {'extra': False, 'named': False, 'root': False, 'type': 'with'},
 {'extra': False, 'named': False, 'root': False, 'type': '{'},
 {'extra': False, 'named': False, 'root': False, 'type': '||'},
 {'extra': False, 'named': False, 'root': False, 'type': '}'}])
__fingerprint__ = ('nix',
 15,
 (0, 1, 0),
 ('end',
  'keyword',
  'identifier',
  'integer_expression',
  'float_expression',
  'path_fragment',
  'spath_expression',
  'uri_expression',
  ':',
  '@',
  '{',
  '}',
  ',',
  '?',
  'ellipses',
  'assert',
  ';',
  'with',
  'let',
  'in',
  'if',
  'then',
  'else',
  '!',
  '-',
  '==',
  '!=',
  '<',
  '<=',
  '>',
  '>=',
  '&&',
  '||',
  '+',
  '*',
  '/',
  '->',
  '//',
  '++',
  '.',
  'or',
  '(',
  ')',
  'rec',
  '"',
  'string_fragment',
  'escape_sequence',
  "''",
  'escape_sequence',
  '=',
  'inherit',
  '${',
  '${',
  '[',
  ']',
  'comment',
  'string_fragment',
  'string_fragment',
  'path_fragment',
  'path_fragment',
  'dollar_escape',
  'dollar_escape',
  'source_code',
  '_expression',
  'variable_expression',
  'path_expression',
  'hpath_expression',
  '_expr_function_expression',
  'function_expression',
  'formals',
  'formal',
  'assert_expression',
  'with_expression',
  'let_expression',
  '_expr_if',
  'if_expression',
  '_expr_op',
  'has_attr_expression',
  'unary_expression',
  'binary_expression',
  '_expr_apply_expression',
  'apply_expression',
  '_expr_select_expression',
  'select_expression',
  '_expr_simple',
  'parenthesized_expression',
  'attrset_expression',
  'let_attrset_expression',
  'rec_attrset_expression',
  'string_expression',
  'indented_string_expression',
  'binding_set',
  'binding',
  'inherit',
  'inherit_from',
  'attrpath',
  'inherited_attrs',
  'interpolation',
  'interpolation',
  'list_expression',
  'path_expression_repeat1',
  'formals_repeat1',
  'string_expression_repeat1',
  'indented_string_expression_repeat1',
  'binding_set_repeat1',
  'attrpath_repeat1',
  'inherited_attrs_repeat1',
  'list_expression_repeat1'),
 ('alternative',
  'argument',
  'attr',
  'attrpath',
  'attrs',
  'binding',
  'body',
  'condition',
  'consequence',
  'default',
  'element',
  'ellipses',
  'environment',
  'expression',
  'formal',
  'formals',
  'function',
  'left',
  'name',
  'operator',
  'right',
  'universal'))

class ApplyExpression(Node):
    __kind__ = 'apply_expression'
    __schema__ = None
    argument: AttrsetExpression | FloatExpression | HpathExpression | IndentedStringExpression | IntegerExpression | LetAttrsetExpression | ListExpression | ParenthesizedExpression | PathExpression | RecAttrsetExpression | SelectExpression | SpathExpression | StringExpression | UriExpression | VariableExpression
    function: ApplyExpression | AttrsetExpression | FloatExpression | HpathExpression | IndentedStringExpression | IntegerExpression | LetAttrsetExpression | ListExpression | ParenthesizedExpression | PathExpression | RecAttrsetExpression | SelectExpression | SpathExpression | StringExpression | UriExpression | VariableExpression

class AssertExpression(Node):
    __kind__ = 'assert_expression'
    __schema__ = None
    body: ApplyExpression | AssertExpression | AttrsetExpression | BinaryExpression | FloatExpression | FunctionExpression | HasAttrExpression | HpathExpression | IfExpression | IndentedStringExpression | IntegerExpression | LetAttrsetExpression | LetExpression | ListExpression | ParenthesizedExpression | PathExpression | RecAttrsetExpression | SelectExpression | SpathExpression | StringExpression | UnaryExpression | UriExpression | VariableExpression | WithExpression
    condition: Expression

class Attrpath(Node):
    __kind__ = 'attrpath'
    __schema__ = None
    attr: list[Identifier | Interpolation | StringExpression]

class AttrsetExpression(Node):
    __kind__ = 'attrset_expression'
    __schema__ = None
    content: BindingSet | None = None

class BinaryExpression(Node):
    __kind__ = 'binary_expression'
    __schema__ = None
    left: ApplyExpression | AttrsetExpression | BinaryExpression | FloatExpression | HasAttrExpression | HpathExpression | IndentedStringExpression | IntegerExpression | LetAttrsetExpression | ListExpression | ParenthesizedExpression | PathExpression | RecAttrsetExpression | SelectExpression | SpathExpression | StringExpression | UnaryExpression | UriExpression | VariableExpression
    operator: _Literal['!='] | _Literal['&&'] | _Literal['*'] | _Literal['+'] | _Literal['++'] | _Literal['-'] | _Literal['->'] | _Literal['/'] | _Literal['//'] | _Literal['<'] | _Literal['<='] | _Literal['=='] | _Literal['>'] | _Literal['>='] | _Literal['||']
    right: ApplyExpression | AttrsetExpression | BinaryExpression | FloatExpression | HasAttrExpression | HpathExpression | IndentedStringExpression | IntegerExpression | LetAttrsetExpression | ListExpression | ParenthesizedExpression | PathExpression | RecAttrsetExpression | SelectExpression | SpathExpression | StringExpression | UnaryExpression | UriExpression | VariableExpression

class Binding(Node):
    __kind__ = 'binding'
    __schema__ = None
    attrpath: Attrpath
    expression: Expression

class BindingSet(Node):
    __kind__ = 'binding_set'
    __schema__ = None
    binding: list[Binding | Inherit | InheritFrom]

class Formal(Node):
    __kind__ = 'formal'
    __schema__ = None
    default: Expression | None = None
    name: Identifier

class Formals(Node):
    __kind__ = 'formals'
    __schema__ = None
    ellipses: Ellipses | None = None
    formal: list[Formal]

class FunctionExpression(Node):
    __kind__ = 'function_expression'
    __schema__ = None
    body: ApplyExpression | AssertExpression | AttrsetExpression | BinaryExpression | FloatExpression | FunctionExpression | HasAttrExpression | HpathExpression | IfExpression | IndentedStringExpression | IntegerExpression | LetAttrsetExpression | LetExpression | ListExpression | ParenthesizedExpression | PathExpression | RecAttrsetExpression | SelectExpression | SpathExpression | StringExpression | UnaryExpression | UriExpression | VariableExpression | WithExpression
    formals: Formals | None = None
    universal: Identifier | None = None

class HasAttrExpression(Node):
    __kind__ = 'has_attr_expression'
    __schema__ = None
    attrpath: Attrpath
    expression: ApplyExpression | AttrsetExpression | BinaryExpression | FloatExpression | HasAttrExpression | HpathExpression | IndentedStringExpression | IntegerExpression | LetAttrsetExpression | ListExpression | ParenthesizedExpression | PathExpression | RecAttrsetExpression | SelectExpression | SpathExpression | StringExpression | UnaryExpression | UriExpression | VariableExpression
    operator: _Literal['?']

class HpathExpression(Node):
    __kind__ = 'hpath_expression'
    __schema__ = None
    content: list[Interpolation | PathFragment]

class IfExpression(Node):
    __kind__ = 'if_expression'
    __schema__ = None
    alternative: Expression
    condition: Expression
    consequence: Expression

class IndentedStringExpression(Node):
    __kind__ = 'indented_string_expression'
    __schema__ = None
    content: list[DollarEscape | EscapeSequence | Interpolation | StringFragment]

class Inherit(Node):
    __kind__ = 'inherit'
    __schema__ = None
    attrs: InheritedAttrs

class InheritFrom(Node):
    __kind__ = 'inherit_from'
    __schema__ = None
    attrs: InheritedAttrs
    expression: Expression

class InheritedAttrs(Node):
    __kind__ = 'inherited_attrs'
    __schema__ = None
    attr: list[Identifier | Interpolation | StringExpression]

class Interpolation(Node):
    __kind__ = 'interpolation'
    __schema__ = None
    expression: Expression

class LetAttrsetExpression(Node):
    __kind__ = 'let_attrset_expression'
    __schema__ = None
    content: BindingSet | None = None

class LetExpression(Node):
    __kind__ = 'let_expression'
    __schema__ = None
    body: ApplyExpression | AssertExpression | AttrsetExpression | BinaryExpression | FloatExpression | FunctionExpression | HasAttrExpression | HpathExpression | IfExpression | IndentedStringExpression | IntegerExpression | LetAttrsetExpression | LetExpression | ListExpression | ParenthesizedExpression | PathExpression | RecAttrsetExpression | SelectExpression | SpathExpression | StringExpression | UnaryExpression | UriExpression | VariableExpression | WithExpression
    content: BindingSet | None = None

class ListExpression(Node):
    __kind__ = 'list_expression'
    __schema__ = None
    element: list[AttrsetExpression | FloatExpression | HpathExpression | IndentedStringExpression | IntegerExpression | LetAttrsetExpression | ListExpression | ParenthesizedExpression | PathExpression | RecAttrsetExpression | SelectExpression | SpathExpression | StringExpression | UriExpression | VariableExpression]

class ParenthesizedExpression(Node):
    __kind__ = 'parenthesized_expression'
    __schema__ = None
    expression: Expression

class PathExpression(Node):
    __kind__ = 'path_expression'
    __schema__ = None
    content: list[Interpolation | PathFragment]

class RecAttrsetExpression(Node):
    __kind__ = 'rec_attrset_expression'
    __schema__ = None
    content: BindingSet | None = None

class SelectExpression(Node):
    __kind__ = 'select_expression'
    __schema__ = None
    attrpath: Attrpath
    default: AttrsetExpression | FloatExpression | HpathExpression | IndentedStringExpression | IntegerExpression | LetAttrsetExpression | ListExpression | ParenthesizedExpression | PathExpression | RecAttrsetExpression | SelectExpression | SpathExpression | StringExpression | UriExpression | VariableExpression | None = None
    expression: AttrsetExpression | FloatExpression | HpathExpression | IndentedStringExpression | IntegerExpression | LetAttrsetExpression | ListExpression | ParenthesizedExpression | PathExpression | RecAttrsetExpression | SpathExpression | StringExpression | UriExpression | VariableExpression

class SourceCode(Node):
    __kind__ = 'source_code'
    __schema__ = None
    expression: Expression | None = None

class StringExpression(Node):
    __kind__ = 'string_expression'
    __schema__ = None
    content: list[DollarEscape | EscapeSequence | Interpolation | StringFragment]

class UnaryExpression(Node):
    __kind__ = 'unary_expression'
    __schema__ = None
    argument: ApplyExpression | AttrsetExpression | BinaryExpression | FloatExpression | HasAttrExpression | HpathExpression | IndentedStringExpression | IntegerExpression | LetAttrsetExpression | ListExpression | ParenthesizedExpression | PathExpression | RecAttrsetExpression | SelectExpression | SpathExpression | StringExpression | UnaryExpression | UriExpression | VariableExpression
    operator: _Literal['!'] | _Literal['-']

class VariableExpression(Node):
    __kind__ = 'variable_expression'
    __schema__ = None
    name: Identifier

class WithExpression(Node):
    __kind__ = 'with_expression'
    __schema__ = None
    body: ApplyExpression | AssertExpression | AttrsetExpression | BinaryExpression | FloatExpression | FunctionExpression | HasAttrExpression | HpathExpression | IfExpression | IndentedStringExpression | IntegerExpression | LetAttrsetExpression | LetExpression | ListExpression | ParenthesizedExpression | PathExpression | RecAttrsetExpression | SelectExpression | SpathExpression | StringExpression | UnaryExpression | UriExpression | VariableExpression | WithExpression
    environment: Expression

class Comment(Node):
    __kind__ = 'comment'
    __schema__ = None

class DollarEscape(Node):
    __kind__ = 'dollar_escape'
    __schema__ = None

class Ellipses(Node):
    __kind__ = 'ellipses'
    __schema__ = None

class EscapeSequence(Node):
    __kind__ = 'escape_sequence'
    __schema__ = None

class FloatExpression(Node):
    __kind__ = 'float_expression'
    __schema__ = None

class Identifier(Node):
    __kind__ = 'identifier'
    __schema__ = None

class IntegerExpression(Node):
    __kind__ = 'integer_expression'
    __schema__ = None

class PathFragment(Node):
    __kind__ = 'path_fragment'
    __schema__ = None

class SpathExpression(Node):
    __kind__ = 'spath_expression'
    __schema__ = None

class StringFragment(Node):
    __kind__ = 'string_fragment'
    __schema__ = None

class UriExpression(Node):
    __kind__ = 'uri_expression'
    __schema__ = None

Expression = ApplyExpression | AssertExpression | AttrsetExpression | BinaryExpression | FloatExpression | FunctionExpression | HasAttrExpression | HpathExpression | IfExpression | IndentedStringExpression | IntegerExpression | LetAttrsetExpression | LetExpression | ListExpression | ParenthesizedExpression | PathExpression | RecAttrsetExpression | SelectExpression | SpathExpression | StringExpression | UnaryExpression | UriExpression | VariableExpression | WithExpression

KIND_MAP = {
    'apply_expression': ApplyExpression,
    'assert_expression': AssertExpression,
    'attrpath': Attrpath,
    'attrset_expression': AttrsetExpression,
    'binary_expression': BinaryExpression,
    'binding': Binding,
    'binding_set': BindingSet,
    'formal': Formal,
    'formals': Formals,
    'function_expression': FunctionExpression,
    'has_attr_expression': HasAttrExpression,
    'hpath_expression': HpathExpression,
    'if_expression': IfExpression,
    'indented_string_expression': IndentedStringExpression,
    'inherit': Inherit,
    'inherit_from': InheritFrom,
    'inherited_attrs': InheritedAttrs,
    'interpolation': Interpolation,
    'let_attrset_expression': LetAttrsetExpression,
    'let_expression': LetExpression,
    'list_expression': ListExpression,
    'parenthesized_expression': ParenthesizedExpression,
    'path_expression': PathExpression,
    'rec_attrset_expression': RecAttrsetExpression,
    'select_expression': SelectExpression,
    'source_code': SourceCode,
    'string_expression': StringExpression,
    'unary_expression': UnaryExpression,
    'variable_expression': VariableExpression,
    'with_expression': WithExpression,
    'comment': Comment,
    'dollar_escape': DollarEscape,
    'ellipses': Ellipses,
    'escape_sequence': EscapeSequence,
    'float_expression': FloatExpression,
    'identifier': Identifier,
    'integer_expression': IntegerExpression,
    'path_fragment': PathFragment,
    'spath_expression': SpathExpression,
    'string_fragment': StringFragment,
    'uri_expression': UriExpression,
}

for _node_class in KIND_MAP.values():
    _node_class.__schema__ = __schema__
    NodeMeta.rebuild(_node_class, globals())

grammar = Grammar._from_generated(__name__, '', __fingerprint__)
