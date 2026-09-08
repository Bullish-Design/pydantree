"""Generated typed nodes; edit the schema or generator, not this file."""
from __future__ import annotations

from typing import Literal as _Literal

from pydantree_sitter import Grammar, Node
from pydantree_sitter.nodes import NodeMeta
from pydantree_sitter.schema import NodeSchema

__schema__ = NodeSchema.from_list([{'extra': False,
  'named': True,
  'root': False,
  'subtypes': [{'named': True, 'type': '_primary_expression'},
               {'named': True, 'type': 'binary_expression'},
               {'named': True, 'type': 'concatenation'},
               {'named': True, 'type': 'parenthesized_expression'},
               {'named': True, 'type': 'postfix_expression'},
               {'named': True, 'type': 'ternary_expression'},
               {'named': True, 'type': 'unary_expression'},
               {'named': True, 'type': 'word'}],
  'type': '_expression'},
 {'extra': False,
  'named': True,
  'root': False,
  'subtypes': [{'named': True, 'type': 'ansi_c_string'},
               {'named': True, 'type': 'arithmetic_expansion'},
               {'named': True, 'type': 'brace_expression'},
               {'named': True, 'type': 'command_substitution'},
               {'named': True, 'type': 'expansion'},
               {'named': True, 'type': 'number'},
               {'named': True, 'type': 'process_substitution'},
               {'named': True, 'type': 'raw_string'},
               {'named': True, 'type': 'simple_expansion'},
               {'named': True, 'type': 'string'},
               {'named': True, 'type': 'translated_string'},
               {'named': True, 'type': 'word'}],
  'type': '_primary_expression'},
 {'extra': False,
  'named': True,
  'root': False,
  'subtypes': [{'named': True, 'type': 'c_style_for_statement'},
               {'named': True, 'type': 'case_statement'},
               {'named': True, 'type': 'command'},
               {'named': True, 'type': 'compound_statement'},
               {'named': True, 'type': 'declaration_command'},
               {'named': True, 'type': 'for_statement'},
               {'named': True, 'type': 'function_definition'},
               {'named': True, 'type': 'if_statement'},
               {'named': True, 'type': 'list'},
               {'named': True, 'type': 'negated_command'},
               {'named': True, 'type': 'pipeline'},
               {'named': True, 'type': 'redirected_statement'},
               {'named': True, 'type': 'subshell'},
               {'named': True, 'type': 'test_command'},
               {'named': True, 'type': 'unset_command'},
               {'named': True, 'type': 'variable_assignment'},
               {'named': True, 'type': 'variable_assignments'},
               {'named': True, 'type': 'while_statement'}],
  'type': '_statement'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'binary_expression'},
                         {'named': True, 'type': 'command_substitution'},
                         {'named': True, 'type': 'expansion'},
                         {'named': True, 'type': 'number'},
                         {'named': True, 'type': 'parenthesized_expression'},
                         {'named': True, 'type': 'postfix_expression'},
                         {'named': True, 'type': 'raw_string'},
                         {'named': True, 'type': 'simple_expansion'},
                         {'named': True, 'type': 'string'},
                         {'named': True, 'type': 'subscript'},
                         {'named': True, 'type': 'ternary_expression'},
                         {'named': True, 'type': 'unary_expression'},
                         {'named': True, 'type': 'variable_name'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'arithmetic_expansion'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_primary_expression'},
                         {'named': True, 'type': 'concatenation'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'array'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'binary_expression'},
                         {'named': True, 'type': 'expansion'},
                         {'named': True, 'type': 'number'},
                         {'named': True, 'type': 'variable_name'}]},
  'extra': False,
  'fields': {'left': {'multiple': False,
                      'required': False,
                      'types': [{'named': True, 'type': '_expression'},
                                {'named': True, 'type': 'command_substitution'},
                                {'named': True, 'type': 'expansion'},
                                {'named': True, 'type': 'number'},
                                {'named': True, 'type': 'raw_string'},
                                {'named': True, 'type': 'simple_expansion'},
                                {'named': True, 'type': 'string'},
                                {'named': True, 'type': 'subscript'},
                                {'named': True, 'type': 'variable_name'}]},
             'operator': {'multiple': False,
                          'required': True,
                          'types': [{'named': False, 'type': '!='},
                                    {'named': False, 'type': '%'},
                                    {'named': False, 'type': '%='},
                                    {'named': False, 'type': '&'},
                                    {'named': False, 'type': '&&'},
                                    {'named': False, 'type': '&='},
                                    {'named': False, 'type': '*'},
                                    {'named': False, 'type': '**'},
                                    {'named': False, 'type': '**='},
                                    {'named': False, 'type': '*='},
                                    {'named': False, 'type': '+'},
                                    {'named': False, 'type': '+='},
                                    {'named': False, 'type': '-'},
                                    {'named': False, 'type': '-='},
                                    {'named': False, 'type': '-a'},
                                    {'named': False, 'type': '-o'},
                                    {'named': False, 'type': '/'},
                                    {'named': False, 'type': '/='},
                                    {'named': False, 'type': '<'},
                                    {'named': False, 'type': '<<'},
                                    {'named': False, 'type': '<<='},
                                    {'named': False, 'type': '<='},
                                    {'named': False, 'type': '='},
                                    {'named': False, 'type': '=='},
                                    {'named': False, 'type': '=~'},
                                    {'named': False, 'type': '>'},
                                    {'named': False, 'type': '>='},
                                    {'named': False, 'type': '>>'},
                                    {'named': False, 'type': '>>='},
                                    {'named': False, 'type': '^'},
                                    {'named': False, 'type': '^='},
                                    {'named': True, 'type': 'test_operator'},
                                    {'named': False, 'type': '|'},
                                    {'named': False, 'type': '|='},
                                    {'named': False, 'type': '||'}]},
             'right': {'multiple': True,
                       'required': False,
                       'types': [{'named': True, 'type': '_expression'},
                                 {'named': True, 'type': 'command_substitution'},
                                 {'named': True, 'type': 'expansion'},
                                 {'named': True, 'type': 'extglob_pattern'},
                                 {'named': True, 'type': 'number'},
                                 {'named': True, 'type': 'raw_string'},
                                 {'named': True, 'type': 'regex'},
                                 {'named': True, 'type': 'simple_expansion'},
                                 {'named': True, 'type': 'string'},
                                 {'named': True, 'type': 'subscript'},
                                 {'named': True, 'type': 'variable_name'}]}},
  'named': True,
  'root': False,
  'type': 'binary_expression'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'number'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'brace_expression'},
 {'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'compound_statement'},
                                {'named': True, 'type': 'do_group'}]},
             'condition': {'multiple': True,
                           'required': False,
                           'types': [{'named': False, 'type': ','},
                                     {'named': True, 'type': 'binary_expression'},
                                     {'named': True, 'type': 'command_substitution'},
                                     {'named': True, 'type': 'expansion'},
                                     {'named': True, 'type': 'number'},
                                     {'named': True,
                                      'type': 'parenthesized_expression'},
                                     {'named': True, 'type': 'postfix_expression'},
                                     {'named': True, 'type': 'simple_expansion'},
                                     {'named': True, 'type': 'string'},
                                     {'named': True, 'type': 'unary_expression'},
                                     {'named': True, 'type': 'variable_assignment'},
                                     {'named': True, 'type': 'word'}]},
             'initializer': {'multiple': True,
                             'required': False,
                             'types': [{'named': False, 'type': ','},
                                       {'named': True, 'type': 'binary_expression'},
                                       {'named': True, 'type': 'command_substitution'},
                                       {'named': True, 'type': 'expansion'},
                                       {'named': True, 'type': 'number'},
                                       {'named': True,
                                        'type': 'parenthesized_expression'},
                                       {'named': True, 'type': 'postfix_expression'},
                                       {'named': True, 'type': 'simple_expansion'},
                                       {'named': True, 'type': 'string'},
                                       {'named': True, 'type': 'unary_expression'},
                                       {'named': True, 'type': 'variable_assignment'},
                                       {'named': True, 'type': 'word'}]},
             'update': {'multiple': True,
                        'required': False,
                        'types': [{'named': False, 'type': ','},
                                  {'named': True, 'type': 'binary_expression'},
                                  {'named': True, 'type': 'command_substitution'},
                                  {'named': True, 'type': 'expansion'},
                                  {'named': True, 'type': 'number'},
                                  {'named': True, 'type': 'parenthesized_expression'},
                                  {'named': True, 'type': 'postfix_expression'},
                                  {'named': True, 'type': 'simple_expansion'},
                                  {'named': True, 'type': 'string'},
                                  {'named': True, 'type': 'unary_expression'},
                                  {'named': True, 'type': 'variable_assignment'},
                                  {'named': True, 'type': 'word'}]}},
  'named': True,
  'root': False,
  'type': 'c_style_for_statement'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_statement'}]},
  'extra': False,
  'fields': {'fallthrough': {'multiple': False,
                             'required': False,
                             'types': [{'named': False, 'type': ';&'},
                                       {'named': False, 'type': ';;&'}]},
             'termination': {'multiple': False,
                             'required': False,
                             'types': [{'named': False, 'type': ';;'}]},
             'value': {'multiple': True,
                       'required': True,
                       'types': [{'named': True, 'type': '_primary_expression'},
                                 {'named': True, 'type': 'concatenation'},
                                 {'named': True, 'type': 'extglob_pattern'}]}},
  'named': True,
  'root': False,
  'type': 'case_item'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'case_item'}]},
  'extra': False,
  'fields': {'value': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': '_primary_expression'},
                                 {'named': True, 'type': 'concatenation'}]}},
  'named': True,
  'root': False,
  'type': 'case_statement'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'subshell'},
                         {'named': True, 'type': 'variable_assignment'}]},
  'extra': False,
  'fields': {'argument': {'multiple': True,
                          'required': False,
                          'types': [{'named': False, 'type': '$'},
                                    {'named': False, 'type': '=='},
                                    {'named': False, 'type': '=~'},
                                    {'named': True, 'type': '_primary_expression'},
                                    {'named': True, 'type': 'concatenation'},
                                    {'named': True, 'type': 'regex'}]},
             'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'command_name'}]},
             'redirect': {'multiple': True,
                          'required': False,
                          'types': [{'named': True, 'type': 'file_redirect'},
                                    {'named': True, 'type': 'herestring_redirect'}]}},
  'named': True,
  'root': False,
  'type': 'command'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': '_primary_expression'},
                         {'named': True, 'type': 'concatenation'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'command_name'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_statement'}]},
  'extra': False,
  'fields': {'redirect': {'multiple': False,
                          'required': False,
                          'types': [{'named': True, 'type': 'file_redirect'}]}},
  'named': True,
  'root': False,
  'type': 'command_substitution'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_statement'},
                         {'named': True, 'type': 'binary_expression'},
                         {'named': True, 'type': 'command_substitution'},
                         {'named': True, 'type': 'expansion'},
                         {'named': True, 'type': 'number'},
                         {'named': True, 'type': 'parenthesized_expression'},
                         {'named': True, 'type': 'postfix_expression'},
                         {'named': True, 'type': 'raw_string'},
                         {'named': True, 'type': 'simple_expansion'},
                         {'named': True, 'type': 'string'},
                         {'named': True, 'type': 'subscript'},
                         {'named': True, 'type': 'ternary_expression'},
                         {'named': True, 'type': 'unary_expression'},
                         {'named': True, 'type': 'variable_name'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'compound_statement'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_primary_expression'},
                         {'named': True, 'type': 'array'},
                         {'named': True, 'type': 'variable_name'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'concatenation'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_primary_expression'},
                         {'named': True, 'type': 'concatenation'},
                         {'named': True, 'type': 'variable_assignment'},
                         {'named': True, 'type': 'variable_name'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'declaration_command'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_statement'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'do_group'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_statement'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'elif_clause'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_statement'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'else_clause'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_primary_expression'},
                         {'named': True, 'type': 'array'},
                         {'named': True, 'type': 'binary_expression'},
                         {'named': True, 'type': 'concatenation'},
                         {'named': True, 'type': 'parenthesized_expression'},
                         {'named': True, 'type': 'regex'},
                         {'named': True, 'type': 'special_variable_name'},
                         {'named': True, 'type': 'subscript'},
                         {'named': True, 'type': 'variable_name'}]},
  'extra': False,
  'fields': {'operator': {'multiple': True,
                          'required': False,
                          'types': [{'named': False, 'type': '!'},
                                    {'named': False, 'type': '#'},
                                    {'named': False, 'type': '##'},
                                    {'named': False, 'type': '%'},
                                    {'named': False, 'type': '%%'},
                                    {'named': False, 'type': '*'},
                                    {'named': False, 'type': '+'},
                                    {'named': False, 'type': ','},
                                    {'named': False, 'type': ',,'},
                                    {'named': False, 'type': '-'},
                                    {'named': False, 'type': '/'},
                                    {'named': False, 'type': '/#'},
                                    {'named': False, 'type': '/%'},
                                    {'named': False, 'type': '//'},
                                    {'named': False, 'type': ':'},
                                    {'named': False, 'type': ':+'},
                                    {'named': False, 'type': ':-'},
                                    {'named': False, 'type': ':='},
                                    {'named': False, 'type': ':?'},
                                    {'named': False, 'type': '='},
                                    {'named': False, 'type': '?'},
                                    {'named': False, 'type': '@'},
                                    {'named': False, 'type': 'A'},
                                    {'named': False, 'type': 'E'},
                                    {'named': False, 'type': 'K'},
                                    {'named': False, 'type': 'L'},
                                    {'named': False, 'type': 'P'},
                                    {'named': False, 'type': 'Q'},
                                    {'named': False, 'type': 'U'},
                                    {'named': False, 'type': '^'},
                                    {'named': False, 'type': '^^'},
                                    {'named': False, 'type': 'a'},
                                    {'named': False, 'type': 'k'},
                                    {'named': False, 'type': 'u'}]}},
  'named': True,
  'root': False,
  'type': 'expansion'},
 {'extra': False,
  'fields': {'descriptor': {'multiple': False,
                            'required': False,
                            'types': [{'named': True, 'type': 'file_descriptor'}]},
             'destination': {'multiple': True,
                             'required': False,
                             'types': [{'named': True, 'type': '_primary_expression'},
                                       {'named': True, 'type': 'concatenation'}]}},
  'named': True,
  'root': False,
  'type': 'file_redirect'},
 {'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'do_group'}]},
             'value': {'multiple': True,
                       'required': False,
                       'types': [{'named': True, 'type': '_primary_expression'},
                                 {'named': True, 'type': 'concatenation'}]},
             'variable': {'multiple': False,
                          'required': True,
                          'types': [{'named': True, 'type': 'variable_name'}]}},
  'named': True,
  'root': False,
  'type': 'for_statement'},
 {'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'compound_statement'},
                                {'named': True, 'type': 'if_statement'},
                                {'named': True, 'type': 'subshell'},
                                {'named': True, 'type': 'test_command'}]},
             'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'word'}]},
             'redirect': {'multiple': False,
                          'required': False,
                          'types': [{'named': True, 'type': 'file_redirect'},
                                    {'named': True, 'type': 'herestring_redirect'}]}},
  'named': True,
  'root': False,
  'type': 'function_definition'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'command_substitution'},
                         {'named': True, 'type': 'expansion'},
                         {'named': True, 'type': 'heredoc_content'},
                         {'named': True, 'type': 'simple_expansion'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'heredoc_body'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'heredoc_body'},
                         {'named': True, 'type': 'heredoc_end'},
                         {'named': True, 'type': 'heredoc_start'},
                         {'named': True, 'type': 'pipeline'}]},
  'extra': False,
  'fields': {'argument': {'multiple': True,
                          'required': False,
                          'types': [{'named': True, 'type': '_primary_expression'},
                                    {'named': True, 'type': 'concatenation'}]},
             'descriptor': {'multiple': False,
                            'required': False,
                            'types': [{'named': True, 'type': 'file_descriptor'}]},
             'operator': {'multiple': False,
                          'required': False,
                          'types': [{'named': False, 'type': '&&'},
                                    {'named': False, 'type': '||'}]},
             'redirect': {'multiple': True,
                          'required': False,
                          'types': [{'named': True, 'type': 'file_redirect'},
                                    {'named': True, 'type': 'herestring_redirect'}]},
             'right': {'multiple': False,
                       'required': False,
                       'types': [{'named': True, 'type': '_statement'}]}},
  'named': True,
  'root': False,
  'type': 'heredoc_redirect'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': '_primary_expression'},
                         {'named': True, 'type': 'concatenation'}]},
  'extra': False,
  'fields': {'descriptor': {'multiple': False,
                            'required': False,
                            'types': [{'named': True, 'type': 'file_descriptor'}]}},
  'named': True,
  'root': False,
  'type': 'herestring_redirect'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_statement'},
                         {'named': True, 'type': 'elif_clause'},
                         {'named': True, 'type': 'else_clause'}]},
  'extra': False,
  'fields': {'condition': {'multiple': True,
                           'required': True,
                           'types': [{'named': False, 'type': '&'},
                                     {'named': False, 'type': ';'},
                                     {'named': False, 'type': ';;'},
                                     {'named': True, 'type': '_statement'}]}},
  'named': True,
  'root': False,
  'type': 'if_statement'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_statement'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'list'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'command'},
                         {'named': True, 'type': 'subshell'},
                         {'named': True, 'type': 'test_command'},
                         {'named': True, 'type': 'variable_assignment'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'negated_command'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'command_substitution'},
                         {'named': True, 'type': 'expansion'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'number'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_expression'},
                         {'named': True, 'type': 'command_substitution'},
                         {'named': True, 'type': 'expansion'},
                         {'named': True, 'type': 'number'},
                         {'named': True, 'type': 'raw_string'},
                         {'named': True, 'type': 'simple_expansion'},
                         {'named': True, 'type': 'string'},
                         {'named': True, 'type': 'subscript'},
                         {'named': True, 'type': 'variable_assignment'},
                         {'named': True, 'type': 'variable_name'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'parenthesized_expression'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_statement'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'pipeline'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': '_expression'},
                         {'named': True, 'type': 'command_substitution'},
                         {'named': True, 'type': 'expansion'},
                         {'named': True, 'type': 'number'},
                         {'named': True, 'type': 'raw_string'},
                         {'named': True, 'type': 'simple_expansion'},
                         {'named': True, 'type': 'string'},
                         {'named': True, 'type': 'subscript'},
                         {'named': True, 'type': 'variable_name'}]},
  'extra': False,
  'fields': {'operator': {'multiple': False,
                          'required': True,
                          'types': [{'named': False, 'type': '++'},
                                    {'named': False, 'type': '--'}]}},
  'named': True,
  'root': False,
  'type': 'postfix_expression'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_statement'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'process_substitution'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_statement'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': True,
  'type': 'program'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'herestring_redirect'}]},
  'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': False,
                      'types': [{'named': True, 'type': '_statement'}]},
             'redirect': {'multiple': True,
                          'required': False,
                          'types': [{'named': True, 'type': 'file_redirect'},
                                    {'named': True, 'type': 'heredoc_redirect'},
                                    {'named': True, 'type': 'herestring_redirect'}]}},
  'named': True,
  'root': False,
  'type': 'redirected_statement'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'special_variable_name'},
                         {'named': True, 'type': 'variable_name'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'simple_expansion'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'arithmetic_expansion'},
                         {'named': True, 'type': 'command_substitution'},
                         {'named': True, 'type': 'expansion'},
                         {'named': True, 'type': 'simple_expansion'},
                         {'named': True, 'type': 'string_content'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'string'},
 {'extra': False,
  'fields': {'index': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': '_primary_expression'},
                                 {'named': True, 'type': 'binary_expression'},
                                 {'named': True, 'type': 'compound_statement'},
                                 {'named': True, 'type': 'concatenation'},
                                 {'named': True, 'type': 'subshell'},
                                 {'named': True, 'type': 'unary_expression'}]},
             'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'variable_name'}]}},
  'named': True,
  'root': False,
  'type': 'subscript'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_statement'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'subshell'},
 {'extra': False,
  'fields': {'alternative': {'multiple': False,
                             'required': True,
                             'types': [{'named': True, 'type': '_expression'},
                                       {'named': True, 'type': 'command_substitution'},
                                       {'named': True, 'type': 'expansion'},
                                       {'named': True, 'type': 'number'},
                                       {'named': True, 'type': 'raw_string'},
                                       {'named': True, 'type': 'simple_expansion'},
                                       {'named': True, 'type': 'string'},
                                       {'named': True, 'type': 'subscript'},
                                       {'named': True, 'type': 'variable_name'}]},
             'condition': {'multiple': False,
                           'required': True,
                           'types': [{'named': True, 'type': '_expression'},
                                     {'named': True, 'type': 'command_substitution'},
                                     {'named': True, 'type': 'expansion'},
                                     {'named': True, 'type': 'number'},
                                     {'named': True, 'type': 'raw_string'},
                                     {'named': True, 'type': 'simple_expansion'},
                                     {'named': True, 'type': 'string'},
                                     {'named': True, 'type': 'subscript'},
                                     {'named': True, 'type': 'variable_name'}]},
             'consequence': {'multiple': False,
                             'required': True,
                             'types': [{'named': True, 'type': '_expression'},
                                       {'named': True, 'type': 'command_substitution'},
                                       {'named': True, 'type': 'expansion'},
                                       {'named': True, 'type': 'number'},
                                       {'named': True, 'type': 'raw_string'},
                                       {'named': True, 'type': 'simple_expansion'},
                                       {'named': True, 'type': 'string'},
                                       {'named': True, 'type': 'subscript'},
                                       {'named': True, 'type': 'variable_name'}]}},
  'named': True,
  'root': False,
  'type': 'ternary_expression'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': '_expression'},
                         {'named': True, 'type': 'redirected_statement'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'test_command'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'string'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'translated_string'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': '_expression'},
                         {'named': True, 'type': 'command_substitution'},
                         {'named': True, 'type': 'expansion'},
                         {'named': True, 'type': 'number'},
                         {'named': True, 'type': 'raw_string'},
                         {'named': True, 'type': 'simple_expansion'},
                         {'named': True, 'type': 'string'},
                         {'named': True, 'type': 'subscript'},
                         {'named': True, 'type': 'variable_name'}]},
  'extra': False,
  'fields': {'operator': {'multiple': False,
                          'required': True,
                          'types': [{'named': False, 'type': '!'},
                                    {'named': False, 'type': '+'},
                                    {'named': False, 'type': '++'},
                                    {'named': False, 'type': '-'},
                                    {'named': False, 'type': '--'},
                                    {'named': True, 'type': 'test_operator'},
                                    {'named': False, 'type': '~'}]}},
  'named': True,
  'root': False,
  'type': 'unary_expression'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_primary_expression'},
                         {'named': True, 'type': 'concatenation'},
                         {'named': True, 'type': 'variable_name'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'unset_command'},
 {'extra': False,
  'fields': {'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'subscript'},
                                {'named': True, 'type': 'variable_name'}]},
             'value': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': '_primary_expression'},
                                 {'named': True, 'type': 'array'},
                                 {'named': True, 'type': 'binary_expression'},
                                 {'named': True, 'type': 'concatenation'},
                                 {'named': True, 'type': 'parenthesized_expression'},
                                 {'named': True, 'type': 'postfix_expression'},
                                 {'named': True, 'type': 'unary_expression'},
                                 {'named': True, 'type': 'variable_assignment'}]}},
  'named': True,
  'root': False,
  'type': 'variable_assignment'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'variable_assignment'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'variable_assignments'},
 {'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'do_group'}]},
             'condition': {'multiple': True,
                           'required': True,
                           'types': [{'named': False, 'type': '&'},
                                     {'named': False, 'type': ';'},
                                     {'named': False, 'type': ';;'},
                                     {'named': True, 'type': '_statement'}]}},
  'named': True,
  'root': False,
  'type': 'while_statement'},
 {'extra': False, 'fields': {}, 'named': True, 'root': False, 'type': 'word'},
 {'extra': False, 'named': False, 'root': False, 'type': '!'},
 {'extra': False, 'named': False, 'root': False, 'type': '!='},
 {'extra': False, 'named': False, 'root': False, 'type': '"'},
 {'extra': False, 'named': False, 'root': False, 'type': '#'},
 {'extra': False, 'named': False, 'root': False, 'type': '##'},
 {'extra': False, 'named': False, 'root': False, 'type': '$'},
 {'extra': False, 'named': False, 'root': False, 'type': '$('},
 {'extra': False, 'named': False, 'root': False, 'type': '$(('},
 {'extra': False, 'named': False, 'root': False, 'type': '$['},
 {'extra': False, 'named': False, 'root': False, 'type': '$`'},
 {'extra': False, 'named': False, 'root': False, 'type': '${'},
 {'extra': False, 'named': False, 'root': False, 'type': '%'},
 {'extra': False, 'named': False, 'root': False, 'type': '%%'},
 {'extra': False, 'named': False, 'root': False, 'type': '%='},
 {'extra': False, 'named': False, 'root': False, 'type': '&'},
 {'extra': False, 'named': False, 'root': False, 'type': '&&'},
 {'extra': False, 'named': False, 'root': False, 'type': '&='},
 {'extra': False, 'named': False, 'root': False, 'type': '&>'},
 {'extra': False, 'named': False, 'root': False, 'type': '&>>'},
 {'extra': False, 'named': False, 'root': False, 'type': '('},
 {'extra': False, 'named': False, 'root': False, 'type': '(('},
 {'extra': False, 'named': False, 'root': False, 'type': ')'},
 {'extra': False, 'named': False, 'root': False, 'type': '))'},
 {'extra': False, 'named': False, 'root': False, 'type': '*'},
 {'extra': False, 'named': False, 'root': False, 'type': '**'},
 {'extra': False, 'named': False, 'root': False, 'type': '**='},
 {'extra': False, 'named': False, 'root': False, 'type': '*='},
 {'extra': False, 'named': False, 'root': False, 'type': '+'},
 {'extra': False, 'named': False, 'root': False, 'type': '++'},
 {'extra': False, 'named': False, 'root': False, 'type': '+='},
 {'extra': False, 'named': False, 'root': False, 'type': ','},
 {'extra': False, 'named': False, 'root': False, 'type': ',,'},
 {'extra': False, 'named': False, 'root': False, 'type': '-'},
 {'extra': False, 'named': False, 'root': False, 'type': '--'},
 {'extra': False, 'named': False, 'root': False, 'type': '-='},
 {'extra': False, 'named': False, 'root': False, 'type': '-a'},
 {'extra': False, 'named': False, 'root': False, 'type': '-o'},
 {'extra': False, 'named': False, 'root': False, 'type': '..'},
 {'extra': False, 'named': False, 'root': False, 'type': '/'},
 {'extra': False, 'named': False, 'root': False, 'type': '/#'},
 {'extra': False, 'named': False, 'root': False, 'type': '/%'},
 {'extra': False, 'named': False, 'root': False, 'type': '//'},
 {'extra': False, 'named': False, 'root': False, 'type': '/='},
 {'extra': False, 'named': False, 'root': False, 'type': ':'},
 {'extra': False, 'named': False, 'root': False, 'type': ':+'},
 {'extra': False, 'named': False, 'root': False, 'type': ':-'},
 {'extra': False, 'named': False, 'root': False, 'type': ':='},
 {'extra': False, 'named': False, 'root': False, 'type': ':?'},
 {'extra': False, 'named': False, 'root': False, 'type': ';'},
 {'extra': False, 'named': False, 'root': False, 'type': ';&'},
 {'extra': False, 'named': False, 'root': False, 'type': ';;'},
 {'extra': False, 'named': False, 'root': False, 'type': ';;&'},
 {'extra': False, 'named': False, 'root': False, 'type': '<'},
 {'extra': False, 'named': False, 'root': False, 'type': '<&'},
 {'extra': False, 'named': False, 'root': False, 'type': '<&-'},
 {'extra': False, 'named': False, 'root': False, 'type': '<('},
 {'extra': False, 'named': False, 'root': False, 'type': '<<'},
 {'extra': False, 'named': False, 'root': False, 'type': '<<-'},
 {'extra': False, 'named': False, 'root': False, 'type': '<<<'},
 {'extra': False, 'named': False, 'root': False, 'type': '<<='},
 {'extra': False, 'named': False, 'root': False, 'type': '<='},
 {'extra': False, 'named': False, 'root': False, 'type': '='},
 {'extra': False, 'named': False, 'root': False, 'type': '=='},
 {'extra': False, 'named': False, 'root': False, 'type': '=~'},
 {'extra': False, 'named': False, 'root': False, 'type': '>'},
 {'extra': False, 'named': False, 'root': False, 'type': '>&'},
 {'extra': False, 'named': False, 'root': False, 'type': '>&-'},
 {'extra': False, 'named': False, 'root': False, 'type': '>('},
 {'extra': False, 'named': False, 'root': False, 'type': '>='},
 {'extra': False, 'named': False, 'root': False, 'type': '>>'},
 {'extra': False, 'named': False, 'root': False, 'type': '>>='},
 {'extra': False, 'named': False, 'root': False, 'type': '>|'},
 {'extra': False, 'named': False, 'root': False, 'type': '?'},
 {'extra': False, 'named': False, 'root': False, 'type': '@'},
 {'extra': False, 'named': False, 'root': False, 'type': 'A'},
 {'extra': False, 'named': False, 'root': False, 'type': 'E'},
 {'extra': False, 'named': False, 'root': False, 'type': 'K'},
 {'extra': False, 'named': False, 'root': False, 'type': 'L'},
 {'extra': False, 'named': False, 'root': False, 'type': 'P'},
 {'extra': False, 'named': False, 'root': False, 'type': 'Q'},
 {'extra': False, 'named': False, 'root': False, 'type': 'U'},
 {'extra': False, 'named': False, 'root': False, 'type': '['},
 {'extra': False, 'named': False, 'root': False, 'type': '[['},
 {'extra': False, 'named': False, 'root': False, 'type': ']'},
 {'extra': False, 'named': False, 'root': False, 'type': ']]'},
 {'extra': False, 'named': False, 'root': False, 'type': '^'},
 {'extra': False, 'named': False, 'root': False, 'type': '^='},
 {'extra': False, 'named': False, 'root': False, 'type': '^^'},
 {'extra': False, 'named': False, 'root': False, 'type': '`'},
 {'extra': False, 'named': False, 'root': False, 'type': '``'},
 {'extra': False, 'named': False, 'root': False, 'type': 'a'},
 {'extra': False, 'named': True, 'root': False, 'type': 'ansi_c_string'},
 {'extra': False, 'named': False, 'root': False, 'type': 'case'},
 {'extra': True, 'named': True, 'root': False, 'type': 'comment'},
 {'extra': False, 'named': False, 'root': False, 'type': 'declare'},
 {'extra': False, 'named': False, 'root': False, 'type': 'do'},
 {'extra': False, 'named': False, 'root': False, 'type': 'done'},
 {'extra': False, 'named': False, 'root': False, 'type': 'elif'},
 {'extra': False, 'named': False, 'root': False, 'type': 'else'},
 {'extra': False, 'named': False, 'root': False, 'type': 'esac'},
 {'extra': False, 'named': False, 'root': False, 'type': 'export'},
 {'extra': False, 'named': True, 'root': False, 'type': 'extglob_pattern'},
 {'extra': False, 'named': False, 'root': False, 'type': 'fi'},
 {'extra': False, 'named': True, 'root': False, 'type': 'file_descriptor'},
 {'extra': False, 'named': False, 'root': False, 'type': 'for'},
 {'extra': False, 'named': False, 'root': False, 'type': 'function'},
 {'extra': False, 'named': True, 'root': False, 'type': 'heredoc_content'},
 {'extra': False, 'named': True, 'root': False, 'type': 'heredoc_end'},
 {'extra': False, 'named': True, 'root': False, 'type': 'heredoc_start'},
 {'extra': False, 'named': False, 'root': False, 'type': 'if'},
 {'extra': False, 'named': False, 'root': False, 'type': 'in'},
 {'extra': False, 'named': False, 'root': False, 'type': 'k'},
 {'extra': False, 'named': False, 'root': False, 'type': 'local'},
 {'extra': False, 'named': True, 'root': False, 'type': 'raw_string'},
 {'extra': False, 'named': False, 'root': False, 'type': 'readonly'},
 {'extra': False, 'named': True, 'root': False, 'type': 'regex'},
 {'extra': False, 'named': False, 'root': False, 'type': 'select'},
 {'extra': False, 'named': True, 'root': False, 'type': 'special_variable_name'},
 {'extra': False, 'named': True, 'root': False, 'type': 'string_content'},
 {'extra': False, 'named': True, 'root': False, 'type': 'test_operator'},
 {'extra': False, 'named': False, 'root': False, 'type': 'then'},
 {'extra': False, 'named': False, 'root': False, 'type': 'typeset'},
 {'extra': False, 'named': False, 'root': False, 'type': 'u'},
 {'extra': False, 'named': False, 'root': False, 'type': 'unset'},
 {'extra': False, 'named': False, 'root': False, 'type': 'unsetenv'},
 {'extra': False, 'named': False, 'root': False, 'type': 'until'},
 {'extra': False, 'named': True, 'root': False, 'type': 'variable_name'},
 {'extra': False, 'named': False, 'root': False, 'type': 'while'},
 {'extra': False, 'named': False, 'root': False, 'type': '{'},
 {'extra': False, 'named': False, 'root': False, 'type': '|'},
 {'extra': False, 'named': False, 'root': False, 'type': '|&'},
 {'extra': False, 'named': False, 'root': False, 'type': '|='},
 {'extra': False, 'named': False, 'root': False, 'type': '||'},
 {'extra': False, 'named': False, 'root': False, 'type': '}'},
 {'extra': False, 'named': False, 'root': False, 'type': '~'}])
__fingerprint__ = ('bash',
 15,
 (0, 1, 0),
 ('end',
  'word',
  'for',
  'select',
  'in',
  '((',
  '))',
  ';',
  ',',
  '=',
  '++',
  '--',
  '+=',
  '-=',
  '*=',
  '/=',
  '%=',
  '**=',
  '<<=',
  '>>=',
  '&=',
  '^=',
  '|=',
  '||',
  '-o',
  '&&',
  '-a',
  '|',
  '^',
  '&',
  '==',
  '!=',
  '<',
  '>',
  '<=',
  '>=',
  '<<',
  '>>',
  '+',
  '-',
  '*',
  '/',
  '%',
  '**',
  '(',
  ')',
  'word',
  'while',
  'until',
  'do',
  'done',
  'if',
  'then',
  'fi',
  'elif',
  'else',
  'case',
  'esac',
  ';;',
  ';&',
  ';;&',
  'function',
  '{',
  '}',
  '|&',
  '!',
  '[',
  ']',
  '[[',
  ']]',
  'declare',
  'typeset',
  'export',
  'readonly',
  'local',
  'unset',
  'unsetenv',
  '=~',
  '&>',
  '&>>',
  '<&',
  '>&',
  '>|',
  '<&-',
  '>&-',
  '<<-',
  'heredoc_redirect_token1',
  '<<<',
  '?',
  ':',
  '++',
  '--',
  '-',
  '+',
  '~',
  '$((',
  '$[',
  'number',
  '..',
  '}',
  '``',
  '$',
  '_special_character',
  '"',
  'string_content',
  'raw_string',
  'ansi_c_string',
  'number_token1',
  'number_token2',
  '#',
  '${',
  '}',
  '!',
  '@',
  '*',
  '#',
  '=',
  ':=',
  '-',
  ':-',
  '+',
  ':+',
  '?',
  ':?',
  '%%',
  'regex',
  '//',
  '/#',
  '/%',
  ',,',
  '^^',
  'U',
  'u',
  'L',
  'Q',
  'E',
  'P',
  'A',
  'K',
  'a',
  'k',
  '$(',
  '`',
  '$`',
  '<(',
  '>(',
  'comment',
  'word',
  'variable_name',
  'variable_name',
  'special_variable_name',
  'special_variable_name',
  'heredoc_start',
  'heredoc_body',
  '_heredoc_body_beginning',
  'heredoc_content',
  'heredoc_end',
  'file_descriptor',
  '_empty_value',
  '_concat',
  'variable_name',
  'test_operator',
  'regex',
  'regex',
  'regex',
  'word',
  'extglob_pattern',
  '$',
  '{',
  '##',
  '#',
  '!',
  '=',
  '__error_recovery',
  'program',
  '_statements',
  '_terminated_statement',
  '_statement_not_pipeline',
  'redirected_statement',
  'for_statement',
  'c_style_for_statement',
  '_for_body',
  '_c_expression',
  '_c_expression_not_assignment',
  'variable_assignment',
  'unary_expression',
  'binary_expression',
  'postfix_expression',
  'parenthesized_expression',
  'while_statement',
  'do_group',
  'if_statement',
  'elif_clause',
  'else_clause',
  'case_statement',
  'case_item',
  'case_item',
  'function_definition',
  'compound_statement',
  'subshell',
  'pipeline',
  'list',
  'negated_command',
  'test_command',
  'binary_expression',
  'declaration_command',
  'unset_command',
  'command',
  'command_name',
  'variable_assignment',
  'variable_assignments',
  'subscript',
  'file_redirect',
  'heredoc_redirect',
  'pipeline',
  '_heredoc_expression',
  '_heredoc_command',
  '_heredoc_body',
  'heredoc_body',
  '_simple_heredoc_body',
  'herestring_redirect',
  '_expression',
  'binary_expression',
  'ternary_expression',
  'unary_expression',
  'postfix_expression',
  'parenthesized_expression',
  'arithmetic_expansion',
  'brace_expression',
  '_arithmetic_expression',
  '_arithmetic_literal',
  'binary_expression',
  'ternary_expression',
  'unary_expression',
  'postfix_expression',
  'parenthesized_expression',
  'concatenation',
  'string',
  'translated_string',
  'array',
  'number',
  'simple_expansion',
  'expansion',
  '_expansion_body',
  '_expansion_expression',
  '_expansion_regex',
  '_expansion_regex_replacement',
  '_expansion_regex_removal',
  '_expansion_max_length',
  '_expansion_max_length_expression',
  'binary_expression',
  '_expansion_operator',
  'concatenation',
  'command_substitution',
  'process_substitution',
  '_extglob_blob',
  '_c_terminator',
  '_statements_repeat1',
  'redirected_statement_repeat1',
  'redirected_statement_repeat2',
  'for_statement_repeat1',
  '_for_body_repeat1',
  'if_statement_repeat1',
  'case_statement_repeat1',
  'case_item_repeat1',
  'compound_statement_repeat1',
  'pipeline_repeat1',
  'declaration_command_repeat1',
  'unset_command_repeat1',
  'command_repeat1',
  'command_repeat2',
  'variable_assignments_repeat1',
  'heredoc_body_repeat1',
  '_literal_repeat1',
  'arithmetic_expansion_repeat1',
  'concatenation_repeat1',
  'string_repeat1',
  '_expansion_body_repeat1',
  '_expansion_regex_repeat1',
  '_concatenation_in_expansion_repeat1'),
 ('alternative',
  'argument',
  'body',
  'condition',
  'consequence',
  'descriptor',
  'destination',
  'fallthrough',
  'index',
  'initializer',
  'left',
  'name',
  'operator',
  'redirect',
  'right',
  'termination',
  'update',
  'value',
  'variable'))

class ArithmeticExpansion(Node):
    __kind__ = 'arithmetic_expansion'
    __schema__ = None
    content: list[BinaryExpression | CommandSubstitution | Expansion | Number | ParenthesizedExpression | PostfixExpression | RawString | SimpleExpansion | String | Subscript | TernaryExpression | UnaryExpression | VariableName]

class Array(Node):
    __kind__ = 'array'
    __schema__ = None
    content: list[PrimaryExpression | Concatenation]

class BinaryExpression(Node):
    __kind__ = 'binary_expression'
    __schema__ = None
    left: Expression | CommandSubstitution | Expansion | Number | RawString | SimpleExpansion | String | Subscript | VariableName | None = None
    operator: _Literal['!='] | _Literal['%'] | _Literal['%='] | _Literal['&'] | _Literal['&&'] | _Literal['&='] | _Literal['*'] | _Literal['**'] | _Literal['**='] | _Literal['*='] | _Literal['+'] | _Literal['+='] | _Literal['-'] | _Literal['-='] | _Literal['-a'] | _Literal['-o'] | _Literal['/'] | _Literal['/='] | _Literal['<'] | _Literal['<<'] | _Literal['<<='] | _Literal['<='] | _Literal['='] | _Literal['=='] | _Literal['=~'] | _Literal['>'] | _Literal['>='] | _Literal['>>'] | _Literal['>>='] | _Literal['^'] | _Literal['^='] | TestOperator | _Literal['|'] | _Literal['|='] | _Literal['||']
    right: list[Expression | CommandSubstitution | Expansion | ExtglobPattern | Number | RawString | Regex | SimpleExpansion | String | Subscript | VariableName]
    content: list[BinaryExpression | Expansion | Number | VariableName]

class BraceExpression(Node):
    __kind__ = 'brace_expression'
    __schema__ = None
    content: list[Number]

class CStyleForStatement(Node):
    __kind__ = 'c_style_for_statement'
    __schema__ = None
    body: CompoundStatement | DoGroup
    condition: list[_Literal[','] | BinaryExpression | CommandSubstitution | Expansion | Number | ParenthesizedExpression | PostfixExpression | SimpleExpansion | String | UnaryExpression | VariableAssignment | Word]
    initializer: list[_Literal[','] | BinaryExpression | CommandSubstitution | Expansion | Number | ParenthesizedExpression | PostfixExpression | SimpleExpansion | String | UnaryExpression | VariableAssignment | Word]
    update: list[_Literal[','] | BinaryExpression | CommandSubstitution | Expansion | Number | ParenthesizedExpression | PostfixExpression | SimpleExpansion | String | UnaryExpression | VariableAssignment | Word]

class CaseItem(Node):
    __kind__ = 'case_item'
    __schema__ = None
    fallthrough: _Literal[';&'] | _Literal[';;&'] | None = None
    termination: _Literal[';;'] | None = None
    value: list[PrimaryExpression | Concatenation | ExtglobPattern]
    content: list[Statement]

class CaseStatement(Node):
    __kind__ = 'case_statement'
    __schema__ = None
    value: PrimaryExpression | Concatenation
    content: list[CaseItem]

class Command(Node):
    __kind__ = 'command'
    __schema__ = None
    argument: list[_Literal['$'] | _Literal['=='] | _Literal['=~'] | PrimaryExpression | Concatenation | Regex]
    name: CommandName
    redirect: list[FileRedirect | HerestringRedirect]
    content: list[Subshell | VariableAssignment]

class CommandName(Node):
    __kind__ = 'command_name'
    __schema__ = None
    content: PrimaryExpression | Concatenation

class CommandSubstitution(Node):
    __kind__ = 'command_substitution'
    __schema__ = None
    redirect: FileRedirect | None = None
    content: list[Statement]

class CompoundStatement(Node):
    __kind__ = 'compound_statement'
    __schema__ = None
    content: list[Statement | BinaryExpression | CommandSubstitution | Expansion | Number | ParenthesizedExpression | PostfixExpression | RawString | SimpleExpansion | String | Subscript | TernaryExpression | UnaryExpression | VariableName]

class Concatenation(Node):
    __kind__ = 'concatenation'
    __schema__ = None
    content: list[PrimaryExpression | Array | VariableName]

class DeclarationCommand(Node):
    __kind__ = 'declaration_command'
    __schema__ = None
    content: list[PrimaryExpression | Concatenation | VariableAssignment | VariableName]

class DoGroup(Node):
    __kind__ = 'do_group'
    __schema__ = None
    content: list[Statement]

class ElifClause(Node):
    __kind__ = 'elif_clause'
    __schema__ = None
    content: list[Statement]

class ElseClause(Node):
    __kind__ = 'else_clause'
    __schema__ = None
    content: list[Statement]

class Expansion(Node):
    __kind__ = 'expansion'
    __schema__ = None
    operator: list[_Literal['!'] | _Literal['#'] | _Literal['##'] | _Literal['%'] | _Literal['%%'] | _Literal['*'] | _Literal['+'] | _Literal[','] | _Literal[',,'] | _Literal['-'] | _Literal['/'] | _Literal['/#'] | _Literal['/%'] | _Literal['//'] | _Literal[':'] | _Literal[':+'] | _Literal[':-'] | _Literal[':='] | _Literal[':?'] | _Literal['='] | _Literal['?'] | _Literal['@'] | _Literal['A'] | _Literal['E'] | _Literal['K'] | _Literal['L'] | _Literal['P'] | _Literal['Q'] | _Literal['U'] | _Literal['^'] | _Literal['^^'] | _Literal['a'] | _Literal['k'] | _Literal['u']]
    content: list[PrimaryExpression | Array | BinaryExpression | Concatenation | ParenthesizedExpression | Regex | SpecialVariableName | Subscript | VariableName]

class FileRedirect(Node):
    __kind__ = 'file_redirect'
    __schema__ = None
    descriptor: FileDescriptor | None = None
    destination: list[PrimaryExpression | Concatenation]

class ForStatement(Node):
    __kind__ = 'for_statement'
    __schema__ = None
    body: DoGroup
    value: list[PrimaryExpression | Concatenation]
    variable: VariableName

class FunctionDefinition(Node):
    __kind__ = 'function_definition'
    __schema__ = None
    body: CompoundStatement | IfStatement | Subshell | TestCommand
    name: Word
    redirect: FileRedirect | HerestringRedirect | None = None

class HeredocBody(Node):
    __kind__ = 'heredoc_body'
    __schema__ = None
    content: list[CommandSubstitution | Expansion | HeredocContent | SimpleExpansion]

class HeredocRedirect(Node):
    __kind__ = 'heredoc_redirect'
    __schema__ = None
    argument: list[PrimaryExpression | Concatenation]
    descriptor: FileDescriptor | None = None
    operator: _Literal['&&'] | _Literal['||'] | None = None
    redirect: list[FileRedirect | HerestringRedirect]
    right: Statement | None = None
    content: list[HeredocBody | HeredocEnd | HeredocStart | Pipeline]

class HerestringRedirect(Node):
    __kind__ = 'herestring_redirect'
    __schema__ = None
    descriptor: FileDescriptor | None = None
    content: PrimaryExpression | Concatenation

class IfStatement(Node):
    __kind__ = 'if_statement'
    __schema__ = None
    condition: list[_Literal['&'] | _Literal[';'] | _Literal[';;'] | Statement]
    content: list[Statement | ElifClause | ElseClause]

class List(Node):
    __kind__ = 'list'
    __schema__ = None
    content: list[Statement]

class NegatedCommand(Node):
    __kind__ = 'negated_command'
    __schema__ = None
    content: Command | Subshell | TestCommand | VariableAssignment

class Number(Node):
    __kind__ = 'number'
    __schema__ = None
    content: CommandSubstitution | Expansion | None = None

class ParenthesizedExpression(Node):
    __kind__ = 'parenthesized_expression'
    __schema__ = None
    content: list[Expression | CommandSubstitution | Expansion | Number | RawString | SimpleExpansion | String | Subscript | VariableAssignment | VariableName]

class Pipeline(Node):
    __kind__ = 'pipeline'
    __schema__ = None
    content: list[Statement]

class PostfixExpression(Node):
    __kind__ = 'postfix_expression'
    __schema__ = None
    operator: _Literal['++'] | _Literal['--']
    content: Expression | CommandSubstitution | Expansion | Number | RawString | SimpleExpansion | String | Subscript | VariableName

class ProcessSubstitution(Node):
    __kind__ = 'process_substitution'
    __schema__ = None
    content: list[Statement]

class Program(Node):
    __kind__ = 'program'
    __schema__ = None
    content: list[Statement]

class RedirectedStatement(Node):
    __kind__ = 'redirected_statement'
    __schema__ = None
    body: Statement | None = None
    redirect: list[FileRedirect | HeredocRedirect | HerestringRedirect]
    content: HerestringRedirect | None = None

class SimpleExpansion(Node):
    __kind__ = 'simple_expansion'
    __schema__ = None
    content: SpecialVariableName | VariableName

class String(Node):
    __kind__ = 'string'
    __schema__ = None
    content: list[ArithmeticExpansion | CommandSubstitution | Expansion | SimpleExpansion | StringContent]

class Subscript(Node):
    __kind__ = 'subscript'
    __schema__ = None
    index: PrimaryExpression | BinaryExpression | CompoundStatement | Concatenation | Subshell | UnaryExpression
    name: VariableName

class Subshell(Node):
    __kind__ = 'subshell'
    __schema__ = None
    content: list[Statement]

class TernaryExpression(Node):
    __kind__ = 'ternary_expression'
    __schema__ = None
    alternative: Expression | CommandSubstitution | Expansion | Number | RawString | SimpleExpansion | String | Subscript | VariableName
    condition: Expression | CommandSubstitution | Expansion | Number | RawString | SimpleExpansion | String | Subscript | VariableName
    consequence: Expression | CommandSubstitution | Expansion | Number | RawString | SimpleExpansion | String | Subscript | VariableName

class TestCommand(Node):
    __kind__ = 'test_command'
    __schema__ = None
    content: Expression | RedirectedStatement | None = None

class TranslatedString(Node):
    __kind__ = 'translated_string'
    __schema__ = None
    content: String

class UnaryExpression(Node):
    __kind__ = 'unary_expression'
    __schema__ = None
    operator: _Literal['!'] | _Literal['+'] | _Literal['++'] | _Literal['-'] | _Literal['--'] | TestOperator | _Literal['~']
    content: Expression | CommandSubstitution | Expansion | Number | RawString | SimpleExpansion | String | Subscript | VariableName

class UnsetCommand(Node):
    __kind__ = 'unset_command'
    __schema__ = None
    content: list[PrimaryExpression | Concatenation | VariableName]

class VariableAssignment(Node):
    __kind__ = 'variable_assignment'
    __schema__ = None
    name: Subscript | VariableName
    value: PrimaryExpression | Array | BinaryExpression | Concatenation | ParenthesizedExpression | PostfixExpression | UnaryExpression | VariableAssignment

class VariableAssignments(Node):
    __kind__ = 'variable_assignments'
    __schema__ = None
    content: list[VariableAssignment]

class WhileStatement(Node):
    __kind__ = 'while_statement'
    __schema__ = None
    body: DoGroup
    condition: list[_Literal['&'] | _Literal[';'] | _Literal[';;'] | Statement]

class Word(Node):
    __kind__ = 'word'
    __schema__ = None

class AnsiCString(Node):
    __kind__ = 'ansi_c_string'
    __schema__ = None

class Comment(Node):
    __kind__ = 'comment'
    __schema__ = None

class ExtglobPattern(Node):
    __kind__ = 'extglob_pattern'
    __schema__ = None

class FileDescriptor(Node):
    __kind__ = 'file_descriptor'
    __schema__ = None

class HeredocContent(Node):
    __kind__ = 'heredoc_content'
    __schema__ = None

class HeredocEnd(Node):
    __kind__ = 'heredoc_end'
    __schema__ = None

class HeredocStart(Node):
    __kind__ = 'heredoc_start'
    __schema__ = None

class RawString(Node):
    __kind__ = 'raw_string'
    __schema__ = None

class Regex(Node):
    __kind__ = 'regex'
    __schema__ = None

class SpecialVariableName(Node):
    __kind__ = 'special_variable_name'
    __schema__ = None

class StringContent(Node):
    __kind__ = 'string_content'
    __schema__ = None

class TestOperator(Node):
    __kind__ = 'test_operator'
    __schema__ = None

class VariableName(Node):
    __kind__ = 'variable_name'
    __schema__ = None

PrimaryExpression = AnsiCString | ArithmeticExpansion | BraceExpression | CommandSubstitution | Expansion | Number | ProcessSubstitution | RawString | SimpleExpansion | String | TranslatedString | Word

Statement = CStyleForStatement | CaseStatement | Command | CompoundStatement | DeclarationCommand | ForStatement | FunctionDefinition | IfStatement | List | NegatedCommand | Pipeline | RedirectedStatement | Subshell | TestCommand | UnsetCommand | VariableAssignment | VariableAssignments | WhileStatement

Expression = PrimaryExpression | BinaryExpression | Concatenation | ParenthesizedExpression | PostfixExpression | TernaryExpression | UnaryExpression | Word

KIND_MAP = {
    'arithmetic_expansion': ArithmeticExpansion,
    'array': Array,
    'binary_expression': BinaryExpression,
    'brace_expression': BraceExpression,
    'c_style_for_statement': CStyleForStatement,
    'case_item': CaseItem,
    'case_statement': CaseStatement,
    'command': Command,
    'command_name': CommandName,
    'command_substitution': CommandSubstitution,
    'compound_statement': CompoundStatement,
    'concatenation': Concatenation,
    'declaration_command': DeclarationCommand,
    'do_group': DoGroup,
    'elif_clause': ElifClause,
    'else_clause': ElseClause,
    'expansion': Expansion,
    'file_redirect': FileRedirect,
    'for_statement': ForStatement,
    'function_definition': FunctionDefinition,
    'heredoc_body': HeredocBody,
    'heredoc_redirect': HeredocRedirect,
    'herestring_redirect': HerestringRedirect,
    'if_statement': IfStatement,
    'list': List,
    'negated_command': NegatedCommand,
    'number': Number,
    'parenthesized_expression': ParenthesizedExpression,
    'pipeline': Pipeline,
    'postfix_expression': PostfixExpression,
    'process_substitution': ProcessSubstitution,
    'program': Program,
    'redirected_statement': RedirectedStatement,
    'simple_expansion': SimpleExpansion,
    'string': String,
    'subscript': Subscript,
    'subshell': Subshell,
    'ternary_expression': TernaryExpression,
    'test_command': TestCommand,
    'translated_string': TranslatedString,
    'unary_expression': UnaryExpression,
    'unset_command': UnsetCommand,
    'variable_assignment': VariableAssignment,
    'variable_assignments': VariableAssignments,
    'while_statement': WhileStatement,
    'word': Word,
    'ansi_c_string': AnsiCString,
    'comment': Comment,
    'extglob_pattern': ExtglobPattern,
    'file_descriptor': FileDescriptor,
    'heredoc_content': HeredocContent,
    'heredoc_end': HeredocEnd,
    'heredoc_start': HeredocStart,
    'raw_string': RawString,
    'regex': Regex,
    'special_variable_name': SpecialVariableName,
    'string_content': StringContent,
    'test_operator': TestOperator,
    'variable_name': VariableName,
}

for _node_class in KIND_MAP.values():
    _node_class.__schema__ = __schema__
    NodeMeta.rebuild(_node_class, globals())

grammar = Grammar._from_generated(__name__, '', __fingerprint__)
