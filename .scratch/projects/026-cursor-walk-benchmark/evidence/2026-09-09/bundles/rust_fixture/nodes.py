"""Generated typed nodes; edit the schema or generator, not this file."""
from __future__ import annotations

from typing import Literal as _Literal

from pydantree_sitter import Grammar, Node
from pydantree_sitter.nodes import NodeMeta
from pydantree_sitter.schema import NodeSchema

__schema__ = NodeSchema.from_list([{'extra': False,
  'named': True,
  'root': False,
  'subtypes': [{'named': True, 'type': 'associated_type'},
               {'named': True, 'type': 'attribute_item'},
               {'named': True, 'type': 'const_item'},
               {'named': True, 'type': 'empty_statement'},
               {'named': True, 'type': 'enum_item'},
               {'named': True, 'type': 'extern_crate_declaration'},
               {'named': True, 'type': 'foreign_mod_item'},
               {'named': True, 'type': 'function_item'},
               {'named': True, 'type': 'function_signature_item'},
               {'named': True, 'type': 'impl_item'},
               {'named': True, 'type': 'inner_attribute_item'},
               {'named': True, 'type': 'let_declaration'},
               {'named': True, 'type': 'macro_definition'},
               {'named': True, 'type': 'macro_invocation'},
               {'named': True, 'type': 'mod_item'},
               {'named': True, 'type': 'static_item'},
               {'named': True, 'type': 'struct_item'},
               {'named': True, 'type': 'trait_item'},
               {'named': True, 'type': 'type_item'},
               {'named': True, 'type': 'union_item'},
               {'named': True, 'type': 'use_declaration'}],
  'type': '_declaration_statement'},
 {'extra': False,
  'named': True,
  'root': False,
  'subtypes': [{'named': True, 'type': '_literal'},
               {'named': True, 'type': 'array_expression'},
               {'named': True, 'type': 'assignment_expression'},
               {'named': True, 'type': 'async_block'},
               {'named': True, 'type': 'await_expression'},
               {'named': True, 'type': 'binary_expression'},
               {'named': True, 'type': 'block'},
               {'named': True, 'type': 'break_expression'},
               {'named': True, 'type': 'call_expression'},
               {'named': True, 'type': 'closure_expression'},
               {'named': True, 'type': 'compound_assignment_expr'},
               {'named': True, 'type': 'const_block'},
               {'named': True, 'type': 'continue_expression'},
               {'named': True, 'type': 'field_expression'},
               {'named': True, 'type': 'for_expression'},
               {'named': True, 'type': 'gen_block'},
               {'named': True, 'type': 'generic_function'},
               {'named': True, 'type': 'identifier'},
               {'named': True, 'type': 'if_expression'},
               {'named': True, 'type': 'index_expression'},
               {'named': True, 'type': 'loop_expression'},
               {'named': True, 'type': 'macro_invocation'},
               {'named': True, 'type': 'match_expression'},
               {'named': True, 'type': 'metavariable'},
               {'named': True, 'type': 'parenthesized_expression'},
               {'named': True, 'type': 'range_expression'},
               {'named': True, 'type': 'reference_expression'},
               {'named': True, 'type': 'return_expression'},
               {'named': True, 'type': 'scoped_identifier'},
               {'named': True, 'type': 'self'},
               {'named': True, 'type': 'struct_expression'},
               {'named': True, 'type': 'try_block'},
               {'named': True, 'type': 'try_expression'},
               {'named': True, 'type': 'tuple_expression'},
               {'named': True, 'type': 'type_cast_expression'},
               {'named': True, 'type': 'unary_expression'},
               {'named': True, 'type': 'unit_expression'},
               {'named': True, 'type': 'unsafe_block'},
               {'named': True, 'type': 'while_expression'},
               {'named': True, 'type': 'yield_expression'}],
  'type': '_expression'},
 {'extra': False,
  'named': True,
  'root': False,
  'subtypes': [{'named': True, 'type': 'boolean_literal'},
               {'named': True, 'type': 'char_literal'},
               {'named': True, 'type': 'float_literal'},
               {'named': True, 'type': 'integer_literal'},
               {'named': True, 'type': 'raw_string_literal'},
               {'named': True, 'type': 'string_literal'}],
  'type': '_literal'},
 {'extra': False,
  'named': True,
  'root': False,
  'subtypes': [{'named': True, 'type': 'boolean_literal'},
               {'named': True, 'type': 'char_literal'},
               {'named': True, 'type': 'float_literal'},
               {'named': True, 'type': 'integer_literal'},
               {'named': True, 'type': 'negative_literal'},
               {'named': True, 'type': 'raw_string_literal'},
               {'named': True, 'type': 'string_literal'}],
  'type': '_literal_pattern'},
 {'extra': False,
  'named': True,
  'root': False,
  'subtypes': [{'named': False, 'type': '_'},
               {'named': True, 'type': '_literal_pattern'},
               {'named': True, 'type': 'captured_pattern'},
               {'named': True, 'type': 'const_block'},
               {'named': True, 'type': 'generic_pattern'},
               {'named': True, 'type': 'identifier'},
               {'named': True, 'type': 'macro_invocation'},
               {'named': True, 'type': 'mut_pattern'},
               {'named': True, 'type': 'or_pattern'},
               {'named': True, 'type': 'range_pattern'},
               {'named': True, 'type': 'ref_pattern'},
               {'named': True, 'type': 'reference_pattern'},
               {'named': True, 'type': 'remaining_field_pattern'},
               {'named': True, 'type': 'scoped_identifier'},
               {'named': True, 'type': 'slice_pattern'},
               {'named': True, 'type': 'struct_pattern'},
               {'named': True, 'type': 'tuple_pattern'},
               {'named': True, 'type': 'tuple_struct_pattern'}],
  'type': '_pattern'},
 {'extra': False,
  'named': True,
  'root': False,
  'subtypes': [{'named': True, 'type': 'abstract_type'},
               {'named': True, 'type': 'array_type'},
               {'named': True, 'type': 'bounded_type'},
               {'named': True, 'type': 'dynamic_type'},
               {'named': True, 'type': 'function_type'},
               {'named': True, 'type': 'generic_type'},
               {'named': True, 'type': 'macro_invocation'},
               {'named': True, 'type': 'metavariable'},
               {'named': True, 'type': 'never_type'},
               {'named': True, 'type': 'pointer_type'},
               {'named': True, 'type': 'primitive_type'},
               {'named': True, 'type': 'reference_type'},
               {'named': True, 'type': 'removed_trait_bound'},
               {'named': True, 'type': 'scoped_type_identifier'},
               {'named': True, 'type': 'tuple_type'},
               {'named': True, 'type': 'type_identifier'},
               {'named': True, 'type': 'unit_type'}],
  'type': '_type'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'type_parameters'}]},
  'extra': False,
  'fields': {'trait': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': 'bounded_type'},
                                 {'named': True, 'type': 'function_type'},
                                 {'named': True, 'type': 'generic_type'},
                                 {'named': True, 'type': 'removed_trait_bound'},
                                 {'named': True, 'type': 'scoped_type_identifier'},
                                 {'named': True, 'type': 'tuple_type'},
                                 {'named': True, 'type': 'type_identifier'}]}},
  'named': True,
  'root': False,
  'type': 'abstract_type'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_expression'},
                         {'named': True, 'type': 'attribute_item'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'arguments'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_expression'},
                         {'named': True, 'type': 'attribute_item'}]},
  'extra': False,
  'fields': {'length': {'multiple': False,
                        'required': False,
                        'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'array_expression'},
 {'extra': False,
  'fields': {'element': {'multiple': False,
                         'required': True,
                         'types': [{'named': True, 'type': '_type'}]},
             'length': {'multiple': False,
                        'required': False,
                        'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'array_type'},
 {'extra': False,
  'fields': {'left': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': '_expression'}]},
             'right': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'assignment_expression'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'where_clause'}]},
  'extra': False,
  'fields': {'bounds': {'multiple': False,
                        'required': False,
                        'types': [{'named': True, 'type': 'trait_bounds'}]},
             'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'type_identifier'}]},
             'type_parameters': {'multiple': False,
                                 'required': False,
                                 'types': [{'named': True,
                                            'type': 'type_parameters'}]}},
  'named': True,
  'root': False,
  'type': 'associated_type'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'block'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'async_block'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'crate'},
                         {'named': True, 'type': 'identifier'},
                         {'named': True, 'type': 'metavariable'},
                         {'named': True, 'type': 'scoped_identifier'},
                         {'named': True, 'type': 'self'},
                         {'named': True, 'type': 'super'}]},
  'extra': False,
  'fields': {'arguments': {'multiple': False,
                           'required': False,
                           'types': [{'named': True, 'type': 'token_tree'}]},
             'value': {'multiple': False,
                       'required': False,
                       'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'attribute'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'attribute'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'attribute_item'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': '_expression'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'await_expression'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': '_expression'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'base_field_initializer'},
 {'extra': False,
  'fields': {'left': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': '_expression'}]},
             'operator': {'multiple': False,
                          'required': True,
                          'types': [{'named': False, 'type': '!='},
                                    {'named': False, 'type': '%'},
                                    {'named': False, 'type': '&'},
                                    {'named': False, 'type': '&&'},
                                    {'named': False, 'type': '*'},
                                    {'named': False, 'type': '+'},
                                    {'named': False, 'type': '-'},
                                    {'named': False, 'type': '/'},
                                    {'named': False, 'type': '<'},
                                    {'named': False, 'type': '<<'},
                                    {'named': False, 'type': '<='},
                                    {'named': False, 'type': '=='},
                                    {'named': False, 'type': '>'},
                                    {'named': False, 'type': '>='},
                                    {'named': False, 'type': '>>'},
                                    {'named': False, 'type': '^'},
                                    {'named': False, 'type': '|'},
                                    {'named': False, 'type': '||'}]},
             'right': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'binary_expression'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_declaration_statement'},
                         {'named': True, 'type': '_expression'},
                         {'named': True, 'type': 'expression_statement'},
                         {'named': True, 'type': 'label'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'block'},
 {'extra': False,
  'fields': {'doc': {'multiple': False,
                     'required': False,
                     'types': [{'named': True, 'type': 'doc_comment'}]},
             'inner': {'multiple': False,
                       'required': False,
                       'types': [{'named': True, 'type': 'inner_doc_comment_marker'}]},
             'outer': {'multiple': False,
                       'required': False,
                       'types': [{'named': True, 'type': 'outer_doc_comment_marker'}]}},
  'named': True,
  'root': False,
  'type': 'block_comment'},
 {'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'boolean_literal'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_type'},
                         {'named': True, 'type': 'lifetime'},
                         {'named': True, 'type': 'use_bounds'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'bounded_type'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': '_type'},
                         {'named': True, 'type': 'qualified_type'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'bracketed_type'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_expression'},
                         {'named': True, 'type': 'label'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'break_expression'},
 {'extra': False,
  'fields': {'arguments': {'multiple': False,
                           'required': True,
                           'types': [{'named': True, 'type': 'arguments'}]},
             'function': {'multiple': False,
                          'required': True,
                          'types': [{'named': True, 'type': '_literal'},
                                    {'named': True, 'type': 'array_expression'},
                                    {'named': True, 'type': 'assignment_expression'},
                                    {'named': True, 'type': 'async_block'},
                                    {'named': True, 'type': 'await_expression'},
                                    {'named': True, 'type': 'binary_expression'},
                                    {'named': True, 'type': 'block'},
                                    {'named': True, 'type': 'break_expression'},
                                    {'named': True, 'type': 'call_expression'},
                                    {'named': True, 'type': 'closure_expression'},
                                    {'named': True, 'type': 'compound_assignment_expr'},
                                    {'named': True, 'type': 'const_block'},
                                    {'named': True, 'type': 'continue_expression'},
                                    {'named': True, 'type': 'field_expression'},
                                    {'named': True, 'type': 'for_expression'},
                                    {'named': True, 'type': 'gen_block'},
                                    {'named': True, 'type': 'generic_function'},
                                    {'named': True, 'type': 'identifier'},
                                    {'named': True, 'type': 'if_expression'},
                                    {'named': True, 'type': 'index_expression'},
                                    {'named': True, 'type': 'loop_expression'},
                                    {'named': True, 'type': 'macro_invocation'},
                                    {'named': True, 'type': 'match_expression'},
                                    {'named': True, 'type': 'metavariable'},
                                    {'named': True, 'type': 'parenthesized_expression'},
                                    {'named': True, 'type': 'reference_expression'},
                                    {'named': True, 'type': 'return_expression'},
                                    {'named': True, 'type': 'scoped_identifier'},
                                    {'named': True, 'type': 'self'},
                                    {'named': True, 'type': 'struct_expression'},
                                    {'named': True, 'type': 'try_block'},
                                    {'named': True, 'type': 'try_expression'},
                                    {'named': True, 'type': 'tuple_expression'},
                                    {'named': True, 'type': 'type_cast_expression'},
                                    {'named': True, 'type': 'unary_expression'},
                                    {'named': True, 'type': 'unit_expression'},
                                    {'named': True, 'type': 'unsafe_block'},
                                    {'named': True, 'type': 'while_expression'},
                                    {'named': True, 'type': 'yield_expression'}]}},
  'named': True,
  'root': False,
  'type': 'call_expression'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_pattern'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'captured_pattern'},
 {'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': False, 'type': '_'},
                                {'named': True, 'type': '_expression'}]},
             'parameters': {'multiple': False,
                            'required': True,
                            'types': [{'named': True, 'type': 'closure_parameters'}]},
             'return_type': {'multiple': False,
                             'required': False,
                             'types': [{'named': True, 'type': '_type'}]}},
  'named': True,
  'root': False,
  'type': 'closure_expression'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_pattern'},
                         {'named': True, 'type': 'parameter'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'closure_parameters'},
 {'extra': False,
  'fields': {'left': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': '_expression'}]},
             'operator': {'multiple': False,
                          'required': True,
                          'types': [{'named': False, 'type': '%='},
                                    {'named': False, 'type': '&='},
                                    {'named': False, 'type': '*='},
                                    {'named': False, 'type': '+='},
                                    {'named': False, 'type': '-='},
                                    {'named': False, 'type': '/='},
                                    {'named': False, 'type': '<<='},
                                    {'named': False, 'type': '>>='},
                                    {'named': False, 'type': '^='},
                                    {'named': False, 'type': '|='}]},
             'right': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'compound_assignment_expr'},
 {'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'block'}]}},
  'named': True,
  'root': False,
  'type': 'const_block'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'visibility_modifier'}]},
  'extra': False,
  'fields': {'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'identifier'}]},
             'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': '_type'}]},
             'value': {'multiple': False,
                       'required': False,
                       'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'const_item'},
 {'extra': False,
  'fields': {'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'identifier'}]},
             'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': '_type'}]},
             'value': {'multiple': False,
                       'required': False,
                       'types': [{'named': True, 'type': '_literal'},
                                 {'named': True, 'type': 'block'},
                                 {'named': True, 'type': 'identifier'},
                                 {'named': True, 'type': 'negative_literal'}]}},
  'named': True,
  'root': False,
  'type': 'const_parameter'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'label'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'continue_expression'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_declaration_statement'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'declaration_list'},
 {'extra': False,
  'fields': {'trait': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': 'function_type'},
                                 {'named': True, 'type': 'generic_type'},
                                 {'named': True, 'type': 'higher_ranked_trait_bound'},
                                 {'named': True, 'type': 'scoped_type_identifier'},
                                 {'named': True, 'type': 'tuple_type'},
                                 {'named': True, 'type': 'type_identifier'}]}},
  'named': True,
  'root': False,
  'type': 'dynamic_type'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'block'},
                         {'named': True, 'type': 'if_expression'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'else_clause'},
 {'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'empty_statement'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'visibility_modifier'},
                         {'named': True, 'type': 'where_clause'}]},
  'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'enum_variant_list'}]},
             'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'type_identifier'}]},
             'type_parameters': {'multiple': False,
                                 'required': False,
                                 'types': [{'named': True,
                                            'type': 'type_parameters'}]}},
  'named': True,
  'root': False,
  'type': 'enum_item'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'visibility_modifier'}]},
  'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': False,
                      'types': [{'named': True, 'type': 'field_declaration_list'},
                                {'named': True,
                                 'type': 'ordered_field_declaration_list'}]},
             'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'identifier'}]},
             'value': {'multiple': False,
                       'required': False,
                       'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'enum_variant'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'attribute_item'},
                         {'named': True, 'type': 'enum_variant'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'enum_variant_list'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': '_expression'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'expression_statement'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'crate'},
                         {'named': True, 'type': 'visibility_modifier'}]},
  'extra': False,
  'fields': {'alias': {'multiple': False,
                       'required': False,
                       'types': [{'named': True, 'type': 'identifier'}]},
             'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'identifier'}]}},
  'named': True,
  'root': False,
  'type': 'extern_crate_declaration'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'string_literal'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'extern_modifier'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'visibility_modifier'}]},
  'extra': False,
  'fields': {'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'field_identifier'}]},
             'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': '_type'}]}},
  'named': True,
  'root': False,
  'type': 'field_declaration'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'attribute_item'},
                         {'named': True, 'type': 'field_declaration'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'field_declaration_list'},
 {'extra': False,
  'fields': {'field': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': 'field_identifier'},
                                 {'named': True, 'type': 'integer_literal'}]},
             'value': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'field_expression'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'attribute_item'}]},
  'extra': False,
  'fields': {'field': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': 'field_identifier'},
                                 {'named': True, 'type': 'integer_literal'}]},
             'value': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'field_initializer'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'base_field_initializer'},
                         {'named': True, 'type': 'field_initializer'},
                         {'named': True, 'type': 'shorthand_field_initializer'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'field_initializer_list'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'mutable_specifier'}]},
  'extra': False,
  'fields': {'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'field_identifier'},
                                {'named': True, 'type': 'shorthand_field_identifier'}]},
             'pattern': {'multiple': False,
                         'required': False,
                         'types': [{'named': True, 'type': '_pattern'}]}},
  'named': True,
  'root': False,
  'type': 'field_pattern'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'label'}]},
  'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'block'}]},
             'pattern': {'multiple': False,
                         'required': True,
                         'types': [{'named': True, 'type': '_pattern'}]},
             'value': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'for_expression'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'lifetime'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'for_lifetimes'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'extern_modifier'}]},
  'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': False,
                      'types': [{'named': True, 'type': 'declaration_list'}]}},
  'named': True,
  'root': False,
  'type': 'foreign_mod_item'},
 {'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'fragment_specifier'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'function_modifiers'},
                         {'named': True, 'type': 'visibility_modifier'},
                         {'named': True, 'type': 'where_clause'}]},
  'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'block'}]},
             'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'identifier'},
                                {'named': True, 'type': 'metavariable'}]},
             'parameters': {'multiple': False,
                            'required': True,
                            'types': [{'named': True, 'type': 'parameters'}]},
             'return_type': {'multiple': False,
                             'required': False,
                             'types': [{'named': True, 'type': '_type'}]},
             'type_parameters': {'multiple': False,
                                 'required': False,
                                 'types': [{'named': True,
                                            'type': 'type_parameters'}]}},
  'named': True,
  'root': False,
  'type': 'function_item'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'extern_modifier'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'function_modifiers'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'function_modifiers'},
                         {'named': True, 'type': 'visibility_modifier'},
                         {'named': True, 'type': 'where_clause'}]},
  'extra': False,
  'fields': {'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'identifier'},
                                {'named': True, 'type': 'metavariable'}]},
             'parameters': {'multiple': False,
                            'required': True,
                            'types': [{'named': True, 'type': 'parameters'}]},
             'return_type': {'multiple': False,
                             'required': False,
                             'types': [{'named': True, 'type': '_type'}]},
             'type_parameters': {'multiple': False,
                                 'required': False,
                                 'types': [{'named': True,
                                            'type': 'type_parameters'}]}},
  'named': True,
  'root': False,
  'type': 'function_signature_item'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'for_lifetimes'},
                         {'named': True, 'type': 'function_modifiers'}]},
  'extra': False,
  'fields': {'parameters': {'multiple': False,
                            'required': True,
                            'types': [{'named': True, 'type': 'parameters'}]},
             'return_type': {'multiple': False,
                             'required': False,
                             'types': [{'named': True, 'type': '_type'}]},
             'trait': {'multiple': False,
                       'required': False,
                       'types': [{'named': True, 'type': 'scoped_type_identifier'},
                                 {'named': True, 'type': 'type_identifier'}]}},
  'named': True,
  'root': False,
  'type': 'function_type'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'block'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'gen_block'},
 {'extra': False,
  'fields': {'function': {'multiple': False,
                          'required': True,
                          'types': [{'named': True, 'type': 'field_expression'},
                                    {'named': True, 'type': 'identifier'},
                                    {'named': True, 'type': 'scoped_identifier'}]},
             'type_arguments': {'multiple': False,
                                'required': True,
                                'types': [{'named': True, 'type': 'type_arguments'}]}},
  'named': True,
  'root': False,
  'type': 'generic_function'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'identifier'},
                         {'named': True, 'type': 'scoped_identifier'}]},
  'extra': False,
  'fields': {'type_arguments': {'multiple': False,
                                'required': True,
                                'types': [{'named': True, 'type': 'type_arguments'}]}},
  'named': True,
  'root': False,
  'type': 'generic_pattern'},
 {'extra': False,
  'fields': {'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'identifier'},
                                {'named': True, 'type': 'scoped_identifier'},
                                {'named': True, 'type': 'scoped_type_identifier'},
                                {'named': True, 'type': 'type_identifier'}]},
             'type_arguments': {'multiple': False,
                                'required': True,
                                'types': [{'named': True, 'type': 'type_arguments'}]}},
  'named': True,
  'root': False,
  'type': 'generic_type'},
 {'extra': False,
  'fields': {'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'scoped_identifier'},
                                {'named': True, 'type': 'type_identifier'}]},
             'type_arguments': {'multiple': False,
                                'required': True,
                                'types': [{'named': True, 'type': 'type_arguments'}]}},
  'named': True,
  'root': False,
  'type': 'generic_type_with_turbofish'},
 {'extra': False,
  'fields': {'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': '_type'}]},
             'type_parameters': {'multiple': False,
                                 'required': True,
                                 'types': [{'named': True,
                                            'type': 'type_parameters'}]}},
  'named': True,
  'root': False,
  'type': 'higher_ranked_trait_bound'},
 {'extra': False,
  'fields': {'alternative': {'multiple': False,
                             'required': False,
                             'types': [{'named': True, 'type': 'else_clause'}]},
             'condition': {'multiple': False,
                           'required': True,
                           'types': [{'named': True, 'type': '_expression'},
                                     {'named': True, 'type': 'let_chain'},
                                     {'named': True, 'type': 'let_condition'}]},
             'consequence': {'multiple': False,
                             'required': True,
                             'types': [{'named': True, 'type': 'block'}]}},
  'named': True,
  'root': False,
  'type': 'if_expression'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'where_clause'}]},
  'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': False,
                      'types': [{'named': True, 'type': 'declaration_list'}]},
             'trait': {'multiple': False,
                       'required': False,
                       'types': [{'named': True, 'type': 'generic_type'},
                                 {'named': True, 'type': 'scoped_type_identifier'},
                                 {'named': True, 'type': 'type_identifier'}]},
             'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': '_type'}]},
             'type_parameters': {'multiple': False,
                                 'required': False,
                                 'types': [{'named': True,
                                            'type': 'type_parameters'}]}},
  'named': True,
  'root': False,
  'type': 'impl_item'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_expression'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'index_expression'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'attribute'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'inner_attribute_item'},
 {'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'inner_doc_comment_marker'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'identifier'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'label'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_expression'},
                         {'named': True, 'type': 'let_condition'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'let_chain'},
 {'extra': False,
  'fields': {'pattern': {'multiple': False,
                         'required': True,
                         'types': [{'named': True, 'type': '_pattern'}]},
             'value': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'let_condition'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'mutable_specifier'}]},
  'extra': False,
  'fields': {'alternative': {'multiple': False,
                             'required': False,
                             'types': [{'named': True, 'type': 'block'}]},
             'pattern': {'multiple': False,
                         'required': True,
                         'types': [{'named': True, 'type': '_pattern'}]},
             'type': {'multiple': False,
                      'required': False,
                      'types': [{'named': True, 'type': '_type'}]},
             'value': {'multiple': False,
                       'required': False,
                       'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'let_declaration'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'identifier'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'lifetime'},
 {'extra': False,
  'fields': {'bounds': {'multiple': False,
                        'required': False,
                        'types': [{'named': True, 'type': 'trait_bounds'}]},
             'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'lifetime'}]}},
  'named': True,
  'root': False,
  'type': 'lifetime_parameter'},
 {'extra': False,
  'fields': {'doc': {'multiple': False,
                     'required': False,
                     'types': [{'named': True, 'type': 'doc_comment'}]},
             'inner': {'multiple': False,
                       'required': False,
                       'types': [{'named': True, 'type': 'inner_doc_comment_marker'}]},
             'outer': {'multiple': False,
                       'required': False,
                       'types': [{'named': True, 'type': 'outer_doc_comment_marker'}]}},
  'named': True,
  'root': False,
  'type': 'line_comment'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'label'}]},
  'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'block'}]}},
  'named': True,
  'root': False,
  'type': 'loop_expression'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'macro_rule'}]},
  'extra': False,
  'fields': {'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'identifier'}]}},
  'named': True,
  'root': False,
  'type': 'macro_definition'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'token_tree'}]},
  'extra': False,
  'fields': {'macro': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': 'identifier'},
                                 {'named': True, 'type': 'scoped_identifier'}]}},
  'named': True,
  'root': False,
  'type': 'macro_invocation'},
 {'extra': False,
  'fields': {'left': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'token_tree_pattern'}]},
             'right': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': 'token_tree'}]}},
  'named': True,
  'root': False,
  'type': 'macro_rule'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'attribute_item'},
                         {'named': True, 'type': 'inner_attribute_item'}]},
  'extra': False,
  'fields': {'pattern': {'multiple': False,
                         'required': True,
                         'types': [{'named': True, 'type': 'match_pattern'}]},
             'value': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'match_arm'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'match_arm'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'match_block'},
 {'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'match_block'}]},
             'value': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'match_expression'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': '_pattern'}]},
  'extra': False,
  'fields': {'condition': {'multiple': False,
                           'required': False,
                           'types': [{'named': True, 'type': '_expression'},
                                     {'named': True, 'type': 'let_chain'},
                                     {'named': True, 'type': 'let_condition'}]}},
  'named': True,
  'root': False,
  'type': 'match_pattern'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'visibility_modifier'}]},
  'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': False,
                      'types': [{'named': True, 'type': 'declaration_list'}]},
             'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'identifier'}]}},
  'named': True,
  'root': False,
  'type': 'mod_item'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_pattern'},
                         {'named': True, 'type': 'mutable_specifier'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'mut_pattern'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'float_literal'},
                         {'named': True, 'type': 'integer_literal'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'negative_literal'},
 {'extra': False, 'fields': {}, 'named': True, 'root': False, 'type': 'never_type'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_pattern'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'or_pattern'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'attribute_item'},
                         {'named': True, 'type': 'visibility_modifier'}]},
  'extra': False,
  'fields': {'type': {'multiple': True,
                      'required': False,
                      'types': [{'named': True, 'type': '_type'}]}},
  'named': True,
  'root': False,
  'type': 'ordered_field_declaration_list'},
 {'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'outer_doc_comment_marker'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'mutable_specifier'}]},
  'extra': False,
  'fields': {'pattern': {'multiple': False,
                         'required': True,
                         'types': [{'named': True, 'type': '_pattern'},
                                   {'named': True, 'type': 'self'}]},
             'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': '_type'}]}},
  'named': True,
  'root': False,
  'type': 'parameter'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_type'},
                         {'named': True, 'type': 'attribute_item'},
                         {'named': True, 'type': 'parameter'},
                         {'named': True, 'type': 'self_parameter'},
                         {'named': True, 'type': 'variadic_parameter'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'parameters'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': '_expression'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'parenthesized_expression'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'mutable_specifier'}]},
  'extra': False,
  'fields': {'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': '_type'}]}},
  'named': True,
  'root': False,
  'type': 'pointer_type'},
 {'extra': False,
  'fields': {'alias': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': '_type'}]},
             'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': '_type'}]}},
  'named': True,
  'root': False,
  'type': 'qualified_type'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_expression'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'range_expression'},
 {'extra': False,
  'fields': {'left': {'multiple': False,
                      'required': False,
                      'types': [{'named': True, 'type': '_literal_pattern'},
                                {'named': True, 'type': 'crate'},
                                {'named': True, 'type': 'identifier'},
                                {'named': True, 'type': 'metavariable'},
                                {'named': True, 'type': 'scoped_identifier'},
                                {'named': True, 'type': 'self'},
                                {'named': True, 'type': 'super'}]},
             'right': {'multiple': False,
                       'required': False,
                       'types': [{'named': True, 'type': '_literal_pattern'},
                                 {'named': True, 'type': 'crate'},
                                 {'named': True, 'type': 'identifier'},
                                 {'named': True, 'type': 'metavariable'},
                                 {'named': True, 'type': 'scoped_identifier'},
                                 {'named': True, 'type': 'self'},
                                 {'named': True, 'type': 'super'}]}},
  'named': True,
  'root': False,
  'type': 'range_pattern'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'string_content'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'raw_string_literal'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': '_pattern'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'ref_pattern'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'mutable_specifier'}]},
  'extra': False,
  'fields': {'value': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'reference_expression'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_pattern'},
                         {'named': True, 'type': 'mutable_specifier'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'reference_pattern'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'lifetime'},
                         {'named': True, 'type': 'mutable_specifier'}]},
  'extra': False,
  'fields': {'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': '_type'}]}},
  'named': True,
  'root': False,
  'type': 'reference_type'},
 {'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'remaining_field_pattern'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': '_type'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'removed_trait_bound'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': '_expression'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'return_expression'},
 {'extra': False,
  'fields': {'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'identifier'},
                                {'named': True, 'type': 'super'}]},
             'path': {'multiple': False,
                      'required': False,
                      'types': [{'named': True, 'type': 'bracketed_type'},
                                {'named': True, 'type': 'crate'},
                                {'named': True, 'type': 'generic_type'},
                                {'named': True, 'type': 'identifier'},
                                {'named': True, 'type': 'metavariable'},
                                {'named': True, 'type': 'scoped_identifier'},
                                {'named': True, 'type': 'self'},
                                {'named': True, 'type': 'super'}]}},
  'named': True,
  'root': False,
  'type': 'scoped_identifier'},
 {'extra': False,
  'fields': {'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'type_identifier'}]},
             'path': {'multiple': False,
                      'required': False,
                      'types': [{'named': True, 'type': 'bracketed_type'},
                                {'named': True, 'type': 'crate'},
                                {'named': True, 'type': 'generic_type'},
                                {'named': True, 'type': 'identifier'},
                                {'named': True, 'type': 'metavariable'},
                                {'named': True, 'type': 'scoped_identifier'},
                                {'named': True, 'type': 'self'},
                                {'named': True, 'type': 'super'}]}},
  'named': True,
  'root': False,
  'type': 'scoped_type_identifier'},
 {'extra': False,
  'fields': {'list': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'use_list'}]},
             'path': {'multiple': False,
                      'required': False,
                      'types': [{'named': True, 'type': 'crate'},
                                {'named': True, 'type': 'identifier'},
                                {'named': True, 'type': 'metavariable'},
                                {'named': True, 'type': 'scoped_identifier'},
                                {'named': True, 'type': 'self'},
                                {'named': True, 'type': 'super'}]}},
  'named': True,
  'root': False,
  'type': 'scoped_use_list'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'lifetime'},
                         {'named': True, 'type': 'mutable_specifier'},
                         {'named': True, 'type': 'self'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'self_parameter'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'attribute_item'},
                         {'named': True, 'type': 'identifier'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'shorthand_field_initializer'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_pattern'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'slice_pattern'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_declaration_statement'},
                         {'named': True, 'type': 'expression_statement'},
                         {'named': True, 'type': 'shebang'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': True,
  'type': 'source_file'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'mutable_specifier'},
                         {'named': True, 'type': 'visibility_modifier'}]},
  'extra': False,
  'fields': {'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'identifier'}]},
             'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': '_type'}]},
             'value': {'multiple': False,
                       'required': False,
                       'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'static_item'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'escape_sequence'},
                         {'named': True, 'type': 'string_content'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'string_literal'},
 {'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'field_initializer_list'}]},
             'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'generic_type_with_turbofish'},
                                {'named': True, 'type': 'scoped_type_identifier'},
                                {'named': True, 'type': 'type_identifier'}]}},
  'named': True,
  'root': False,
  'type': 'struct_expression'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'visibility_modifier'},
                         {'named': True, 'type': 'where_clause'}]},
  'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': False,
                      'types': [{'named': True, 'type': 'field_declaration_list'},
                                {'named': True,
                                 'type': 'ordered_field_declaration_list'}]},
             'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'type_identifier'}]},
             'type_parameters': {'multiple': False,
                                 'required': False,
                                 'types': [{'named': True,
                                            'type': 'type_parameters'}]}},
  'named': True,
  'root': False,
  'type': 'struct_item'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'field_pattern'},
                         {'named': True, 'type': 'remaining_field_pattern'}]},
  'extra': False,
  'fields': {'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'scoped_type_identifier'},
                                {'named': True, 'type': 'type_identifier'}]}},
  'named': True,
  'root': False,
  'type': 'struct_pattern'},
 {'extra': False,
  'fields': {'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'metavariable'}]},
             'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'fragment_specifier'}]}},
  'named': True,
  'root': False,
  'type': 'token_binding_pattern'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_literal'},
                         {'named': True, 'type': 'crate'},
                         {'named': True, 'type': 'identifier'},
                         {'named': True, 'type': 'metavariable'},
                         {'named': True, 'type': 'mutable_specifier'},
                         {'named': True, 'type': 'primitive_type'},
                         {'named': True, 'type': 'self'},
                         {'named': True, 'type': 'super'},
                         {'named': True, 'type': 'token_repetition'},
                         {'named': True, 'type': 'token_tree'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'token_repetition'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_literal'},
                         {'named': True, 'type': 'crate'},
                         {'named': True, 'type': 'identifier'},
                         {'named': True, 'type': 'metavariable'},
                         {'named': True, 'type': 'mutable_specifier'},
                         {'named': True, 'type': 'primitive_type'},
                         {'named': True, 'type': 'self'},
                         {'named': True, 'type': 'super'},
                         {'named': True, 'type': 'token_binding_pattern'},
                         {'named': True, 'type': 'token_repetition_pattern'},
                         {'named': True, 'type': 'token_tree_pattern'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'token_repetition_pattern'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_literal'},
                         {'named': True, 'type': 'crate'},
                         {'named': True, 'type': 'identifier'},
                         {'named': True, 'type': 'metavariable'},
                         {'named': True, 'type': 'mutable_specifier'},
                         {'named': True, 'type': 'primitive_type'},
                         {'named': True, 'type': 'self'},
                         {'named': True, 'type': 'super'},
                         {'named': True, 'type': 'token_repetition'},
                         {'named': True, 'type': 'token_tree'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'token_tree'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_literal'},
                         {'named': True, 'type': 'crate'},
                         {'named': True, 'type': 'identifier'},
                         {'named': True, 'type': 'metavariable'},
                         {'named': True, 'type': 'mutable_specifier'},
                         {'named': True, 'type': 'primitive_type'},
                         {'named': True, 'type': 'self'},
                         {'named': True, 'type': 'super'},
                         {'named': True, 'type': 'token_binding_pattern'},
                         {'named': True, 'type': 'token_repetition_pattern'},
                         {'named': True, 'type': 'token_tree_pattern'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'token_tree_pattern'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_type'},
                         {'named': True, 'type': 'higher_ranked_trait_bound'},
                         {'named': True, 'type': 'lifetime'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'trait_bounds'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'visibility_modifier'},
                         {'named': True, 'type': 'where_clause'}]},
  'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'declaration_list'}]},
             'bounds': {'multiple': False,
                        'required': False,
                        'types': [{'named': True, 'type': 'trait_bounds'}]},
             'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'type_identifier'}]},
             'type_parameters': {'multiple': False,
                                 'required': False,
                                 'types': [{'named': True,
                                            'type': 'type_parameters'}]}},
  'named': True,
  'root': False,
  'type': 'trait_item'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'block'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'try_block'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': '_expression'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'try_expression'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_expression'},
                         {'named': True, 'type': 'attribute_item'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'tuple_expression'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_pattern'},
                         {'named': True, 'type': 'closure_expression'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'tuple_pattern'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': '_pattern'}]},
  'extra': False,
  'fields': {'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'generic_type'},
                                {'named': True, 'type': 'identifier'},
                                {'named': True, 'type': 'scoped_identifier'}]}},
  'named': True,
  'root': False,
  'type': 'tuple_struct_pattern'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_type'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'tuple_type'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': '_literal'},
                         {'named': True, 'type': '_type'},
                         {'named': True, 'type': 'block'},
                         {'named': True, 'type': 'lifetime'},
                         {'named': True, 'type': 'trait_bounds'},
                         {'named': True, 'type': 'type_binding'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'type_arguments'},
 {'extra': False,
  'fields': {'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'type_identifier'}]},
             'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': '_type'}]},
             'type_arguments': {'multiple': False,
                                'required': False,
                                'types': [{'named': True, 'type': 'type_arguments'}]}},
  'named': True,
  'root': False,
  'type': 'type_binding'},
 {'extra': False,
  'fields': {'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': '_type'}]},
             'value': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': '_expression'}]}},
  'named': True,
  'root': False,
  'type': 'type_cast_expression'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'visibility_modifier'},
                         {'named': True, 'type': 'where_clause'}]},
  'extra': False,
  'fields': {'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'type_identifier'}]},
             'type': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': '_type'}]},
             'type_parameters': {'multiple': False,
                                 'required': False,
                                 'types': [{'named': True,
                                            'type': 'type_parameters'}]}},
  'named': True,
  'root': False,
  'type': 'type_item'},
 {'extra': False,
  'fields': {'bounds': {'multiple': False,
                        'required': False,
                        'types': [{'named': True, 'type': 'trait_bounds'}]},
             'default_type': {'multiple': False,
                              'required': False,
                              'types': [{'named': True, 'type': '_type'}]},
             'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'type_identifier'}]}},
  'named': True,
  'root': False,
  'type': 'type_parameter'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'attribute_item'},
                         {'named': True, 'type': 'const_parameter'},
                         {'named': True, 'type': 'lifetime_parameter'},
                         {'named': True, 'type': 'metavariable'},
                         {'named': True, 'type': 'type_parameter'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'type_parameters'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': '_expression'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'unary_expression'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'visibility_modifier'},
                         {'named': True, 'type': 'where_clause'}]},
  'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'field_declaration_list'}]},
             'name': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'type_identifier'}]},
             'type_parameters': {'multiple': False,
                                 'required': False,
                                 'types': [{'named': True,
                                            'type': 'type_parameters'}]}},
  'named': True,
  'root': False,
  'type': 'union_item'},
 {'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'unit_expression'},
 {'extra': False, 'fields': {}, 'named': True, 'root': False, 'type': 'unit_type'},
 {'children': {'multiple': False,
               'required': True,
               'types': [{'named': True, 'type': 'block'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'unsafe_block'},
 {'extra': False,
  'fields': {'alias': {'multiple': False,
                       'required': True,
                       'types': [{'named': True, 'type': 'identifier'}]},
             'path': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'crate'},
                                {'named': True, 'type': 'identifier'},
                                {'named': True, 'type': 'metavariable'},
                                {'named': True, 'type': 'scoped_identifier'},
                                {'named': True, 'type': 'self'},
                                {'named': True, 'type': 'super'}]}},
  'named': True,
  'root': False,
  'type': 'use_as_clause'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'lifetime'},
                         {'named': True, 'type': 'type_identifier'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'use_bounds'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'visibility_modifier'}]},
  'extra': False,
  'fields': {'argument': {'multiple': False,
                          'required': True,
                          'types': [{'named': True, 'type': 'crate'},
                                    {'named': True, 'type': 'identifier'},
                                    {'named': True, 'type': 'metavariable'},
                                    {'named': True, 'type': 'scoped_identifier'},
                                    {'named': True, 'type': 'scoped_use_list'},
                                    {'named': True, 'type': 'self'},
                                    {'named': True, 'type': 'super'},
                                    {'named': True, 'type': 'use_as_clause'},
                                    {'named': True, 'type': 'use_list'},
                                    {'named': True, 'type': 'use_wildcard'}]}},
  'named': True,
  'root': False,
  'type': 'use_declaration'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'crate'},
                         {'named': True, 'type': 'identifier'},
                         {'named': True, 'type': 'metavariable'},
                         {'named': True, 'type': 'scoped_identifier'},
                         {'named': True, 'type': 'scoped_use_list'},
                         {'named': True, 'type': 'self'},
                         {'named': True, 'type': 'super'},
                         {'named': True, 'type': 'use_as_clause'},
                         {'named': True, 'type': 'use_list'},
                         {'named': True, 'type': 'use_wildcard'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'use_list'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'crate'},
                         {'named': True, 'type': 'identifier'},
                         {'named': True, 'type': 'metavariable'},
                         {'named': True, 'type': 'scoped_identifier'},
                         {'named': True, 'type': 'self'},
                         {'named': True, 'type': 'super'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'use_wildcard'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'mutable_specifier'}]},
  'extra': False,
  'fields': {'pattern': {'multiple': False,
                         'required': False,
                         'types': [{'named': True, 'type': '_pattern'}]}},
  'named': True,
  'root': False,
  'type': 'variadic_parameter'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'crate'},
                         {'named': True, 'type': 'identifier'},
                         {'named': True, 'type': 'metavariable'},
                         {'named': True, 'type': 'scoped_identifier'},
                         {'named': True, 'type': 'self'},
                         {'named': True, 'type': 'super'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'visibility_modifier'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'where_predicate'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'where_clause'},
 {'extra': False,
  'fields': {'bounds': {'multiple': False,
                        'required': True,
                        'types': [{'named': True, 'type': 'trait_bounds'}]},
             'left': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'array_type'},
                                {'named': True, 'type': 'generic_type'},
                                {'named': True, 'type': 'higher_ranked_trait_bound'},
                                {'named': True, 'type': 'lifetime'},
                                {'named': True, 'type': 'pointer_type'},
                                {'named': True, 'type': 'primitive_type'},
                                {'named': True, 'type': 'reference_type'},
                                {'named': True, 'type': 'scoped_type_identifier'},
                                {'named': True, 'type': 'tuple_type'},
                                {'named': True, 'type': 'type_identifier'}]}},
  'named': True,
  'root': False,
  'type': 'where_predicate'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'label'}]},
  'extra': False,
  'fields': {'body': {'multiple': False,
                      'required': True,
                      'types': [{'named': True, 'type': 'block'}]},
             'condition': {'multiple': False,
                           'required': True,
                           'types': [{'named': True, 'type': '_expression'},
                                     {'named': True, 'type': 'let_chain'},
                                     {'named': True, 'type': 'let_condition'}]}},
  'named': True,
  'root': False,
  'type': 'while_expression'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': '_expression'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'yield_expression'},
 {'extra': False, 'named': False, 'root': False, 'type': '!'},
 {'extra': False, 'named': False, 'root': False, 'type': '!='},
 {'extra': False, 'named': False, 'root': False, 'type': '"'},
 {'extra': False, 'named': False, 'root': False, 'type': '#'},
 {'extra': False, 'named': False, 'root': False, 'type': '$'},
 {'extra': False, 'named': False, 'root': False, 'type': '%'},
 {'extra': False, 'named': False, 'root': False, 'type': '%='},
 {'extra': False, 'named': False, 'root': False, 'type': '&'},
 {'extra': False, 'named': False, 'root': False, 'type': '&&'},
 {'extra': False, 'named': False, 'root': False, 'type': '&='},
 {'extra': False, 'named': False, 'root': False, 'type': "'"},
 {'extra': False, 'named': False, 'root': False, 'type': '('},
 {'extra': False, 'named': False, 'root': False, 'type': ')'},
 {'extra': False, 'named': False, 'root': False, 'type': '*'},
 {'extra': False, 'named': False, 'root': False, 'type': '*/'},
 {'extra': False, 'named': False, 'root': False, 'type': '*='},
 {'extra': False, 'named': False, 'root': False, 'type': '+'},
 {'extra': False, 'named': False, 'root': False, 'type': '+='},
 {'extra': False, 'named': False, 'root': False, 'type': ','},
 {'extra': False, 'named': False, 'root': False, 'type': '-'},
 {'extra': False, 'named': False, 'root': False, 'type': '-='},
 {'extra': False, 'named': False, 'root': False, 'type': '->'},
 {'extra': False, 'named': False, 'root': False, 'type': '.'},
 {'extra': False, 'named': False, 'root': False, 'type': '..'},
 {'extra': False, 'named': False, 'root': False, 'type': '...'},
 {'extra': False, 'named': False, 'root': False, 'type': '..='},
 {'extra': False, 'named': False, 'root': False, 'type': '/'},
 {'extra': False, 'named': False, 'root': False, 'type': '/*'},
 {'extra': False, 'named': False, 'root': False, 'type': '//'},
 {'extra': False, 'named': False, 'root': False, 'type': '/='},
 {'extra': False, 'named': False, 'root': False, 'type': ':'},
 {'extra': False, 'named': False, 'root': False, 'type': '::'},
 {'extra': False, 'named': False, 'root': False, 'type': ';'},
 {'extra': False, 'named': False, 'root': False, 'type': '<'},
 {'extra': False, 'named': False, 'root': False, 'type': '<<'},
 {'extra': False, 'named': False, 'root': False, 'type': '<<='},
 {'extra': False, 'named': False, 'root': False, 'type': '<='},
 {'extra': False, 'named': False, 'root': False, 'type': '='},
 {'extra': False, 'named': False, 'root': False, 'type': '=='},
 {'extra': False, 'named': False, 'root': False, 'type': '=>'},
 {'extra': False, 'named': False, 'root': False, 'type': '>'},
 {'extra': False, 'named': False, 'root': False, 'type': '>='},
 {'extra': False, 'named': False, 'root': False, 'type': '>>'},
 {'extra': False, 'named': False, 'root': False, 'type': '>>='},
 {'extra': False, 'named': False, 'root': False, 'type': '?'},
 {'extra': False, 'named': False, 'root': False, 'type': '@'},
 {'extra': False, 'named': False, 'root': False, 'type': '['},
 {'extra': False, 'named': False, 'root': False, 'type': ']'},
 {'extra': False, 'named': False, 'root': False, 'type': '^'},
 {'extra': False, 'named': False, 'root': False, 'type': '^='},
 {'extra': False, 'named': False, 'root': False, 'type': '_'},
 {'extra': False, 'named': False, 'root': False, 'type': 'as'},
 {'extra': False, 'named': False, 'root': False, 'type': 'async'},
 {'extra': False, 'named': False, 'root': False, 'type': 'await'},
 {'extra': False, 'named': False, 'root': False, 'type': 'block'},
 {'extra': False, 'named': False, 'root': False, 'type': 'break'},
 {'extra': False, 'named': True, 'root': False, 'type': 'char_literal'},
 {'extra': False, 'named': False, 'root': False, 'type': 'const'},
 {'extra': False, 'named': False, 'root': False, 'type': 'continue'},
 {'extra': False, 'named': True, 'root': False, 'type': 'crate'},
 {'extra': False, 'named': False, 'root': False, 'type': 'default'},
 {'extra': False, 'named': True, 'root': False, 'type': 'doc_comment'},
 {'extra': False, 'named': False, 'root': False, 'type': 'dyn'},
 {'extra': False, 'named': False, 'root': False, 'type': 'else'},
 {'extra': False, 'named': False, 'root': False, 'type': 'enum'},
 {'extra': False, 'named': True, 'root': False, 'type': 'escape_sequence'},
 {'extra': False, 'named': False, 'root': False, 'type': 'expr'},
 {'extra': False, 'named': False, 'root': False, 'type': 'expr_2021'},
 {'extra': False, 'named': False, 'root': False, 'type': 'extern'},
 {'extra': False, 'named': False, 'root': False, 'type': 'false'},
 {'extra': False, 'named': True, 'root': False, 'type': 'field_identifier'},
 {'extra': False, 'named': True, 'root': False, 'type': 'float_literal'},
 {'extra': False, 'named': False, 'root': False, 'type': 'fn'},
 {'extra': False, 'named': False, 'root': False, 'type': 'for'},
 {'extra': False, 'named': False, 'root': False, 'type': 'gen'},
 {'extra': False, 'named': False, 'root': False, 'type': 'ident'},
 {'extra': False, 'named': True, 'root': False, 'type': 'identifier'},
 {'extra': False, 'named': False, 'root': False, 'type': 'if'},
 {'extra': False, 'named': False, 'root': False, 'type': 'impl'},
 {'extra': False, 'named': False, 'root': False, 'type': 'in'},
 {'extra': False, 'named': True, 'root': False, 'type': 'integer_literal'},
 {'extra': False, 'named': False, 'root': False, 'type': 'item'},
 {'extra': False, 'named': False, 'root': False, 'type': 'let'},
 {'extra': False, 'named': False, 'root': False, 'type': 'lifetime'},
 {'extra': False, 'named': False, 'root': False, 'type': 'literal'},
 {'extra': False, 'named': False, 'root': False, 'type': 'loop'},
 {'extra': False, 'named': False, 'root': False, 'type': 'macro_rules!'},
 {'extra': False, 'named': False, 'root': False, 'type': 'match'},
 {'extra': False, 'named': False, 'root': False, 'type': 'meta'},
 {'extra': False, 'named': True, 'root': False, 'type': 'metavariable'},
 {'extra': False, 'named': False, 'root': False, 'type': 'mod'},
 {'extra': False, 'named': False, 'root': False, 'type': 'move'},
 {'extra': False, 'named': True, 'root': False, 'type': 'mutable_specifier'},
 {'extra': False, 'named': False, 'root': False, 'type': 'pat'},
 {'extra': False, 'named': False, 'root': False, 'type': 'pat_param'},
 {'extra': False, 'named': False, 'root': False, 'type': 'path'},
 {'extra': False, 'named': True, 'root': False, 'type': 'primitive_type'},
 {'extra': False, 'named': False, 'root': False, 'type': 'pub'},
 {'extra': False, 'named': False, 'root': False, 'type': 'raw'},
 {'extra': False, 'named': False, 'root': False, 'type': 'ref'},
 {'extra': False, 'named': False, 'root': False, 'type': 'return'},
 {'extra': False, 'named': True, 'root': False, 'type': 'self'},
 {'extra': False, 'named': True, 'root': False, 'type': 'shebang'},
 {'extra': False, 'named': True, 'root': False, 'type': 'shorthand_field_identifier'},
 {'extra': False, 'named': False, 'root': False, 'type': 'static'},
 {'extra': False, 'named': False, 'root': False, 'type': 'stmt'},
 {'extra': False, 'named': True, 'root': False, 'type': 'string_content'},
 {'extra': False, 'named': False, 'root': False, 'type': 'struct'},
 {'extra': False, 'named': True, 'root': False, 'type': 'super'},
 {'extra': False, 'named': False, 'root': False, 'type': 'trait'},
 {'extra': False, 'named': False, 'root': False, 'type': 'true'},
 {'extra': False, 'named': False, 'root': False, 'type': 'try'},
 {'extra': False, 'named': False, 'root': False, 'type': 'tt'},
 {'extra': False, 'named': False, 'root': False, 'type': 'ty'},
 {'extra': False, 'named': False, 'root': False, 'type': 'type'},
 {'extra': False, 'named': True, 'root': False, 'type': 'type_identifier'},
 {'extra': False, 'named': False, 'root': False, 'type': 'union'},
 {'extra': False, 'named': False, 'root': False, 'type': 'unsafe'},
 {'extra': False, 'named': False, 'root': False, 'type': 'use'},
 {'extra': False, 'named': False, 'root': False, 'type': 'vis'},
 {'extra': False, 'named': False, 'root': False, 'type': 'where'},
 {'extra': False, 'named': False, 'root': False, 'type': 'while'},
 {'extra': False, 'named': False, 'root': False, 'type': 'yield'},
 {'extra': False, 'named': False, 'root': False, 'type': '{'},
 {'extra': False, 'named': False, 'root': False, 'type': '|'},
 {'extra': False, 'named': False, 'root': False, 'type': '|='},
 {'extra': False, 'named': False, 'root': False, 'type': '||'},
 {'extra': False, 'named': False, 'root': False, 'type': '}'}])
__fingerprint__ = ('rust',
 15,
 (0, 1, 0),
 ('end',
  'identifier',
  ';',
  'macro_rules!',
  '(',
  ')',
  '[',
  ']',
  '{',
  '}',
  '=>',
  ':',
  '$',
  'token_repetition_pattern_token1',
  '+',
  '*',
  '?',
  'block',
  'expr',
  'expr_2021',
  'ident',
  'item',
  'lifetime',
  'literal',
  'meta',
  'pat',
  'pat_param',
  'path',
  'stmt',
  'tt',
  'ty',
  'vis',
  'primitive_type',
  'primitive_type',
  'primitive_type',
  'primitive_type',
  'primitive_type',
  'primitive_type',
  'primitive_type',
  'primitive_type',
  'primitive_type',
  'primitive_type',
  'primitive_type',
  'primitive_type',
  'primitive_type',
  'primitive_type',
  'primitive_type',
  'primitive_type',
  'primitive_type',
  '-',
  '/',
  '%',
  '^',
  '!',
  '&',
  '|',
  '&&',
  '||',
  '<<',
  '>>',
  '+=',
  '-=',
  '*=',
  '/=',
  '%=',
  '^=',
  '&=',
  '|=',
  '<<=',
  '>>=',
  '=',
  '==',
  '!=',
  '>',
  '<',
  '>=',
  '<=',
  '@',
  '_',
  '.',
  '..',
  '...',
  '..=',
  ',',
  '::',
  '->',
  '#',
  "'",
  'as',
  'async',
  'await',
  'break',
  'const',
  'continue',
  'default',
  'enum',
  'fn',
  'for',
  'gen',
  'if',
  'impl',
  'let',
  'loop',
  'match',
  'mod',
  'pub',
  'return',
  'static',
  'struct',
  'trait',
  'type',
  'union',
  'unsafe',
  'use',
  'where',
  'while',
  'extern',
  'ref',
  'else',
  'in',
  '<',
  'dyn',
  'mutable_specifier',
  'raw',
  'yield',
  'move',
  'try',
  'integer_literal',
  '"',
  'char_literal',
  'escape_sequence',
  'true',
  'false',
  '//',
  'line_comment_token1',
  'line_comment_token2',
  'line_comment_token3',
  '!',
  '/',
  '/*',
  '*/',
  'shebang',
  'self',
  'super',
  'crate',
  'metavariable',
  'string_content',
  '"',
  '_raw_string_literal_start',
  'string_content',
  '_raw_string_literal_end',
  'float_literal',
  'outer_doc_comment_marker',
  'inner_doc_comment_marker',
  '_block_comment_content',
  'doc_comment',
  '_error_sentinel',
  'source_file',
  '_statement',
  'empty_statement',
  'expression_statement',
  'macro_definition',
  'macro_rule',
  '_token_pattern',
  'token_tree_pattern',
  'token_binding_pattern',
  'token_repetition_pattern',
  'fragment_specifier',
  'token_tree',
  'token_repetition',
  'attribute_item',
  'inner_attribute_item',
  'attribute',
  'mod_item',
  'foreign_mod_item',
  'declaration_list',
  'struct_item',
  'union_item',
  'enum_item',
  'enum_variant_list',
  'enum_variant',
  'field_declaration_list',
  'field_declaration',
  'ordered_field_declaration_list',
  'extern_crate_declaration',
  'const_item',
  'static_item',
  'type_item',
  'function_item',
  'function_signature_item',
  'function_modifiers',
  'where_clause',
  'where_predicate',
  'impl_item',
  'trait_item',
  'associated_type',
  'trait_bounds',
  'higher_ranked_trait_bound',
  'removed_trait_bound',
  'type_parameters',
  'const_parameter',
  'type_parameter',
  'lifetime_parameter',
  'let_declaration',
  'use_declaration',
  '_use_clause',
  'scoped_use_list',
  'use_list',
  'use_as_clause',
  'use_wildcard',
  'parameters',
  'self_parameter',
  'variadic_parameter',
  'parameter',
  'extern_modifier',
  'visibility_modifier',
  '_type',
  'bracketed_type',
  'qualified_type',
  'lifetime',
  'array_type',
  'for_lifetimes',
  'function_type',
  'tuple_type',
  'unit_type',
  'generic_function',
  'generic_type',
  'generic_type_with_turbofish',
  'bounded_type',
  'use_bounds',
  'type_arguments',
  'type_binding',
  'reference_type',
  'pointer_type',
  'never_type',
  'abstract_type',
  'dynamic_type',
  '_expression_except_range',
  '_expression',
  'macro_invocation',
  'token_tree',
  '_delim_tokens',
  '_non_delim_token',
  'scoped_identifier',
  'scoped_type_identifier',
  'scoped_type_identifier',
  'range_expression',
  'unary_expression',
  'try_expression',
  'reference_expression',
  'binary_expression',
  'assignment_expression',
  'compound_assignment_expr',
  'type_cast_expression',
  'return_expression',
  'yield_expression',
  'call_expression',
  'arguments',
  'array_expression',
  'parenthesized_expression',
  'tuple_expression',
  'unit_expression',
  'struct_expression',
  'field_initializer_list',
  'shorthand_field_initializer',
  'field_initializer',
  'base_field_initializer',
  'if_expression',
  'let_condition',
  '_let_chain',
  '_condition',
  'else_clause',
  'match_expression',
  'match_block',
  'match_arm',
  'match_arm',
  'match_pattern',
  'while_expression',
  'loop_expression',
  'for_expression',
  'const_block',
  'closure_expression',
  'closure_parameters',
  'label',
  'break_expression',
  'continue_expression',
  'index_expression',
  'await_expression',
  'field_expression',
  'unsafe_block',
  'async_block',
  'gen_block',
  'try_block',
  'block',
  '_pattern',
  'generic_pattern',
  'tuple_pattern',
  'slice_pattern',
  'tuple_struct_pattern',
  'struct_pattern',
  'field_pattern',
  'remaining_field_pattern',
  'mut_pattern',
  'range_pattern',
  'ref_pattern',
  'captured_pattern',
  'reference_pattern',
  'or_pattern',
  '_literal',
  '_literal_pattern',
  'negative_literal',
  'string_literal',
  'raw_string_literal',
  'boolean_literal',
  'line_comment',
  '_line_doc_comment_marker',
  'inner_doc_comment_marker',
  'outer_doc_comment_marker',
  'block_comment',
  '_block_doc_comment_marker',
  'source_file_repeat1',
  'macro_definition_repeat1',
  'token_tree_pattern_repeat1',
  'token_tree_repeat1',
  '_non_special_token_repeat1',
  'declaration_list_repeat1',
  'enum_variant_list_repeat1',
  'enum_variant_list_repeat2',
  'field_declaration_list_repeat1',
  'ordered_field_declaration_list_repeat1',
  'function_modifiers_repeat1',
  'where_clause_repeat1',
  'trait_bounds_repeat1',
  'type_parameters_repeat1',
  'use_list_repeat1',
  'parameters_repeat1',
  'for_lifetimes_repeat1',
  'tuple_type_repeat1',
  'use_bounds_repeat1',
  'type_arguments_repeat1',
  'delim_token_tree_repeat1',
  'arguments_repeat1',
  'tuple_expression_repeat1',
  'field_initializer_list_repeat1',
  'match_block_repeat1',
  'match_arm_repeat1',
  'closure_parameters_repeat1',
  'tuple_pattern_repeat1',
  'slice_pattern_repeat1',
  'struct_pattern_repeat1',
  'string_literal_repeat1',
  'field_identifier',
  'let_chain',
  'shorthand_field_identifier',
  'type_identifier'),
 ('alias',
  'alternative',
  'argument',
  'arguments',
  'body',
  'bounds',
  'condition',
  'consequence',
  'default_type',
  'doc',
  'element',
  'field',
  'function',
  'inner',
  'left',
  'length',
  'list',
  'macro',
  'name',
  'operator',
  'outer',
  'parameters',
  'path',
  'pattern',
  'return_type',
  'right',
  'trait',
  'type',
  'type_arguments',
  'type_parameters',
  'value'))

class AbstractType(Node):
    __kind__ = 'abstract_type'
    __schema__ = None
    trait: BoundedType | FunctionType | GenericType | RemovedTraitBound | ScopedTypeIdentifier | TupleType | TypeIdentifier
    content: TypeParameters | None = None

class Arguments(Node):
    __kind__ = 'arguments'
    __schema__ = None
    content: list[Expression | AttributeItem]

class ArrayExpression(Node):
    __kind__ = 'array_expression'
    __schema__ = None
    length: Expression | None = None
    content: list[Expression | AttributeItem]

class ArrayType(Node):
    __kind__ = 'array_type'
    __schema__ = None
    element: Type
    length: Expression | None = None

class AssignmentExpression(Node):
    __kind__ = 'assignment_expression'
    __schema__ = None
    left: Expression
    right: Expression

class AssociatedType(Node):
    __kind__ = 'associated_type'
    __schema__ = None
    bounds: TraitBounds | None = None
    name: TypeIdentifier
    type_parameters: TypeParameters | None = None
    content: WhereClause | None = None

class AsyncBlock(Node):
    __kind__ = 'async_block'
    __schema__ = None
    content: Block

class Attribute(Node):
    __kind__ = 'attribute'
    __schema__ = None
    arguments: TokenTree | None = None
    value: Expression | None = None
    content: Crate | Identifier | Metavariable | ScopedIdentifier | Self | Super

class AttributeItem(Node):
    __kind__ = 'attribute_item'
    __schema__ = None
    content: Attribute

class AwaitExpression(Node):
    __kind__ = 'await_expression'
    __schema__ = None
    content: Expression

class BaseFieldInitializer(Node):
    __kind__ = 'base_field_initializer'
    __schema__ = None
    content: Expression

class BinaryExpression(Node):
    __kind__ = 'binary_expression'
    __schema__ = None
    left: Expression
    operator: _Literal['!='] | _Literal['%'] | _Literal['&'] | _Literal['&&'] | _Literal['*'] | _Literal['+'] | _Literal['-'] | _Literal['/'] | _Literal['<'] | _Literal['<<'] | _Literal['<='] | _Literal['=='] | _Literal['>'] | _Literal['>='] | _Literal['>>'] | _Literal['^'] | _Literal['|'] | _Literal['||']
    right: Expression

class Block(Node):
    __kind__ = 'block'
    __schema__ = None
    content: list[DeclarationStatement | Expression | ExpressionStatement | Label]

class BlockComment(Node):
    __kind__ = 'block_comment'
    __schema__ = None
    doc: DocComment | None = None
    inner: InnerDocCommentMarker | None = None
    outer: OuterDocCommentMarker | None = None

class BooleanLiteral(Node):
    __kind__ = 'boolean_literal'
    __schema__ = None

class BoundedType(Node):
    __kind__ = 'bounded_type'
    __schema__ = None
    content: list[Type | Lifetime | UseBounds]

class BracketedType(Node):
    __kind__ = 'bracketed_type'
    __schema__ = None
    content: Type | QualifiedType

class BreakExpression(Node):
    __kind__ = 'break_expression'
    __schema__ = None
    content: list[Expression | Label]

class CallExpression(Node):
    __kind__ = 'call_expression'
    __schema__ = None
    arguments: Arguments
    function: Literal | ArrayExpression | AssignmentExpression | AsyncBlock | AwaitExpression | BinaryExpression | Block | BreakExpression | CallExpression | ClosureExpression | CompoundAssignmentExpr | ConstBlock | ContinueExpression | FieldExpression | ForExpression | GenBlock | GenericFunction | Identifier | IfExpression | IndexExpression | LoopExpression | MacroInvocation | MatchExpression | Metavariable | ParenthesizedExpression | ReferenceExpression | ReturnExpression | ScopedIdentifier | Self | StructExpression | TryBlock | TryExpression | TupleExpression | TypeCastExpression | UnaryExpression | UnitExpression | UnsafeBlock | WhileExpression | YieldExpression

class CapturedPattern(Node):
    __kind__ = 'captured_pattern'
    __schema__ = None
    content: list[Pattern]

class ClosureExpression(Node):
    __kind__ = 'closure_expression'
    __schema__ = None
    body: _Literal['_'] | Expression
    parameters: ClosureParameters
    return_type: Type | None = None

class ClosureParameters(Node):
    __kind__ = 'closure_parameters'
    __schema__ = None
    content: list[Pattern | Parameter]

class CompoundAssignmentExpr(Node):
    __kind__ = 'compound_assignment_expr'
    __schema__ = None
    left: Expression
    operator: _Literal['%='] | _Literal['&='] | _Literal['*='] | _Literal['+='] | _Literal['-='] | _Literal['/='] | _Literal['<<='] | _Literal['>>='] | _Literal['^='] | _Literal['|=']
    right: Expression

class ConstBlock(Node):
    __kind__ = 'const_block'
    __schema__ = None
    body: Block

class ConstItem(Node):
    __kind__ = 'const_item'
    __schema__ = None
    name: Identifier
    type: Type
    value: Expression | None = None
    content: VisibilityModifier | None = None

class ConstParameter(Node):
    __kind__ = 'const_parameter'
    __schema__ = None
    name: Identifier
    type: Type
    value: Literal | Block | Identifier | NegativeLiteral | None = None

class ContinueExpression(Node):
    __kind__ = 'continue_expression'
    __schema__ = None
    content: Label | None = None

class DeclarationList(Node):
    __kind__ = 'declaration_list'
    __schema__ = None
    content: list[DeclarationStatement]

class DynamicType(Node):
    __kind__ = 'dynamic_type'
    __schema__ = None
    trait: FunctionType | GenericType | HigherRankedTraitBound | ScopedTypeIdentifier | TupleType | TypeIdentifier

class ElseClause(Node):
    __kind__ = 'else_clause'
    __schema__ = None
    content: Block | IfExpression

class EmptyStatement(Node):
    __kind__ = 'empty_statement'
    __schema__ = None

class EnumItem(Node):
    __kind__ = 'enum_item'
    __schema__ = None
    body: EnumVariantList
    name: TypeIdentifier
    type_parameters: TypeParameters | None = None
    content: list[VisibilityModifier | WhereClause]

class EnumVariant(Node):
    __kind__ = 'enum_variant'
    __schema__ = None
    body: FieldDeclarationList | OrderedFieldDeclarationList | None = None
    name: Identifier
    value: Expression | None = None
    content: VisibilityModifier | None = None

class EnumVariantList(Node):
    __kind__ = 'enum_variant_list'
    __schema__ = None
    content: list[AttributeItem | EnumVariant]

class ExpressionStatement(Node):
    __kind__ = 'expression_statement'
    __schema__ = None
    content: Expression

class ExternCrateDeclaration(Node):
    __kind__ = 'extern_crate_declaration'
    __schema__ = None
    alias: Identifier | None = None
    name: Identifier
    content: list[Crate | VisibilityModifier]

class ExternModifier(Node):
    __kind__ = 'extern_modifier'
    __schema__ = None
    content: StringLiteral | None = None

class FieldDeclaration(Node):
    __kind__ = 'field_declaration'
    __schema__ = None
    name: FieldIdentifier
    type: Type
    content: VisibilityModifier | None = None

class FieldDeclarationList(Node):
    __kind__ = 'field_declaration_list'
    __schema__ = None
    content: list[AttributeItem | FieldDeclaration]

class FieldExpression(Node):
    __kind__ = 'field_expression'
    __schema__ = None
    field: FieldIdentifier | IntegerLiteral
    value: Expression

class FieldInitializer(Node):
    __kind__ = 'field_initializer'
    __schema__ = None
    field: FieldIdentifier | IntegerLiteral
    value: Expression
    content: list[AttributeItem]

class FieldInitializerList(Node):
    __kind__ = 'field_initializer_list'
    __schema__ = None
    content: list[BaseFieldInitializer | FieldInitializer | ShorthandFieldInitializer]

class FieldPattern(Node):
    __kind__ = 'field_pattern'
    __schema__ = None
    name: FieldIdentifier | ShorthandFieldIdentifier
    pattern: Pattern | None = None
    content: MutableSpecifier | None = None

class ForExpression(Node):
    __kind__ = 'for_expression'
    __schema__ = None
    body: Block
    pattern: Pattern
    value: Expression
    content: Label | None = None

class ForLifetimes(Node):
    __kind__ = 'for_lifetimes'
    __schema__ = None
    content: list[Lifetime]

class ForeignModItem(Node):
    __kind__ = 'foreign_mod_item'
    __schema__ = None
    body: DeclarationList | None = None
    content: ExternModifier

class FragmentSpecifier(Node):
    __kind__ = 'fragment_specifier'
    __schema__ = None

class FunctionItem(Node):
    __kind__ = 'function_item'
    __schema__ = None
    body: Block
    name: Identifier | Metavariable
    parameters: Parameters
    return_type: Type | None = None
    type_parameters: TypeParameters | None = None
    content: list[FunctionModifiers | VisibilityModifier | WhereClause]

class FunctionModifiers(Node):
    __kind__ = 'function_modifiers'
    __schema__ = None
    content: list[ExternModifier]

class FunctionSignatureItem(Node):
    __kind__ = 'function_signature_item'
    __schema__ = None
    name: Identifier | Metavariable
    parameters: Parameters
    return_type: Type | None = None
    type_parameters: TypeParameters | None = None
    content: list[FunctionModifiers | VisibilityModifier | WhereClause]

class FunctionType(Node):
    __kind__ = 'function_type'
    __schema__ = None
    parameters: Parameters
    return_type: Type | None = None
    trait: ScopedTypeIdentifier | TypeIdentifier | None = None
    content: list[ForLifetimes | FunctionModifiers]

class GenBlock(Node):
    __kind__ = 'gen_block'
    __schema__ = None
    content: Block

class GenericFunction(Node):
    __kind__ = 'generic_function'
    __schema__ = None
    function: FieldExpression | Identifier | ScopedIdentifier
    type_arguments: TypeArguments

class GenericPattern(Node):
    __kind__ = 'generic_pattern'
    __schema__ = None
    type_arguments: TypeArguments
    content: Identifier | ScopedIdentifier

class GenericType(Node):
    __kind__ = 'generic_type'
    __schema__ = None
    type: Identifier | ScopedIdentifier | ScopedTypeIdentifier | TypeIdentifier
    type_arguments: TypeArguments

class GenericTypeWithTurbofish(Node):
    __kind__ = 'generic_type_with_turbofish'
    __schema__ = None
    type: ScopedIdentifier | TypeIdentifier
    type_arguments: TypeArguments

class HigherRankedTraitBound(Node):
    __kind__ = 'higher_ranked_trait_bound'
    __schema__ = None
    type: Type
    type_parameters: TypeParameters

class IfExpression(Node):
    __kind__ = 'if_expression'
    __schema__ = None
    alternative: ElseClause | None = None
    condition: Expression | LetChain | LetCondition
    consequence: Block

class ImplItem(Node):
    __kind__ = 'impl_item'
    __schema__ = None
    body: DeclarationList | None = None
    trait: GenericType | ScopedTypeIdentifier | TypeIdentifier | None = None
    type: Type
    type_parameters: TypeParameters | None = None
    content: WhereClause | None = None

class IndexExpression(Node):
    __kind__ = 'index_expression'
    __schema__ = None
    content: list[Expression]

class InnerAttributeItem(Node):
    __kind__ = 'inner_attribute_item'
    __schema__ = None
    content: Attribute

class InnerDocCommentMarker(Node):
    __kind__ = 'inner_doc_comment_marker'
    __schema__ = None

class Label(Node):
    __kind__ = 'label'
    __schema__ = None
    content: Identifier

class LetChain(Node):
    __kind__ = 'let_chain'
    __schema__ = None
    content: list[Expression | LetCondition]

class LetCondition(Node):
    __kind__ = 'let_condition'
    __schema__ = None
    pattern: Pattern
    value: Expression

class LetDeclaration(Node):
    __kind__ = 'let_declaration'
    __schema__ = None
    alternative: Block | None = None
    pattern: Pattern
    type: Type | None = None
    value: Expression | None = None
    content: MutableSpecifier | None = None

class Lifetime(Node):
    __kind__ = 'lifetime'
    __schema__ = None
    content: Identifier

class LifetimeParameter(Node):
    __kind__ = 'lifetime_parameter'
    __schema__ = None
    bounds: TraitBounds | None = None
    name: Lifetime

class LineComment(Node):
    __kind__ = 'line_comment'
    __schema__ = None
    doc: DocComment | None = None
    inner: InnerDocCommentMarker | None = None
    outer: OuterDocCommentMarker | None = None

class LoopExpression(Node):
    __kind__ = 'loop_expression'
    __schema__ = None
    body: Block
    content: Label | None = None

class MacroDefinition(Node):
    __kind__ = 'macro_definition'
    __schema__ = None
    name: Identifier
    content: list[MacroRule]

class MacroInvocation(Node):
    __kind__ = 'macro_invocation'
    __schema__ = None
    macro: Identifier | ScopedIdentifier
    content: TokenTree

class MacroRule(Node):
    __kind__ = 'macro_rule'
    __schema__ = None
    left: TokenTreePattern
    right: TokenTree

class MatchArm(Node):
    __kind__ = 'match_arm'
    __schema__ = None
    pattern: MatchPattern
    value: Expression
    content: list[AttributeItem | InnerAttributeItem]

class MatchBlock(Node):
    __kind__ = 'match_block'
    __schema__ = None
    content: list[MatchArm]

class MatchExpression(Node):
    __kind__ = 'match_expression'
    __schema__ = None
    body: MatchBlock
    value: Expression

class MatchPattern(Node):
    __kind__ = 'match_pattern'
    __schema__ = None
    condition: Expression | LetChain | LetCondition | None = None
    content: Pattern

class ModItem(Node):
    __kind__ = 'mod_item'
    __schema__ = None
    body: DeclarationList | None = None
    name: Identifier
    content: VisibilityModifier | None = None

class MutPattern(Node):
    __kind__ = 'mut_pattern'
    __schema__ = None
    content: list[Pattern | MutableSpecifier]

class NegativeLiteral(Node):
    __kind__ = 'negative_literal'
    __schema__ = None
    content: FloatLiteral | IntegerLiteral

class NeverType(Node):
    __kind__ = 'never_type'
    __schema__ = None

class OrPattern(Node):
    __kind__ = 'or_pattern'
    __schema__ = None
    content: list[Pattern]

class OrderedFieldDeclarationList(Node):
    __kind__ = 'ordered_field_declaration_list'
    __schema__ = None
    type: list[Type]
    content: list[AttributeItem | VisibilityModifier]

class OuterDocCommentMarker(Node):
    __kind__ = 'outer_doc_comment_marker'
    __schema__ = None

class Parameter(Node):
    __kind__ = 'parameter'
    __schema__ = None
    pattern: Pattern | Self
    type: Type
    content: MutableSpecifier | None = None

class Parameters(Node):
    __kind__ = 'parameters'
    __schema__ = None
    content: list[Type | AttributeItem | Parameter | SelfParameter | VariadicParameter]

class ParenthesizedExpression(Node):
    __kind__ = 'parenthesized_expression'
    __schema__ = None
    content: Expression

class PointerType(Node):
    __kind__ = 'pointer_type'
    __schema__ = None
    type: Type
    content: MutableSpecifier | None = None

class QualifiedType(Node):
    __kind__ = 'qualified_type'
    __schema__ = None
    alias: Type
    type: Type

class RangeExpression(Node):
    __kind__ = 'range_expression'
    __schema__ = None
    content: list[Expression]

class RangePattern(Node):
    __kind__ = 'range_pattern'
    __schema__ = None
    left: LiteralPattern | Crate | Identifier | Metavariable | ScopedIdentifier | Self | Super | None = None
    right: LiteralPattern | Crate | Identifier | Metavariable | ScopedIdentifier | Self | Super | None = None

class RawStringLiteral(Node):
    __kind__ = 'raw_string_literal'
    __schema__ = None
    content: StringContent

class RefPattern(Node):
    __kind__ = 'ref_pattern'
    __schema__ = None
    content: Pattern

class ReferenceExpression(Node):
    __kind__ = 'reference_expression'
    __schema__ = None
    value: Expression
    content: MutableSpecifier | None = None

class ReferencePattern(Node):
    __kind__ = 'reference_pattern'
    __schema__ = None
    content: list[Pattern | MutableSpecifier]

class ReferenceType(Node):
    __kind__ = 'reference_type'
    __schema__ = None
    type: Type
    content: list[Lifetime | MutableSpecifier]

class RemainingFieldPattern(Node):
    __kind__ = 'remaining_field_pattern'
    __schema__ = None

class RemovedTraitBound(Node):
    __kind__ = 'removed_trait_bound'
    __schema__ = None
    content: Type

class ReturnExpression(Node):
    __kind__ = 'return_expression'
    __schema__ = None
    content: Expression | None = None

class ScopedIdentifier(Node):
    __kind__ = 'scoped_identifier'
    __schema__ = None
    name: Identifier | Super
    path: BracketedType | Crate | GenericType | Identifier | Metavariable | ScopedIdentifier | Self | Super | None = None

class ScopedTypeIdentifier(Node):
    __kind__ = 'scoped_type_identifier'
    __schema__ = None
    name: TypeIdentifier
    path: BracketedType | Crate | GenericType | Identifier | Metavariable | ScopedIdentifier | Self | Super | None = None

class ScopedUseList(Node):
    __kind__ = 'scoped_use_list'
    __schema__ = None
    list: UseList
    path: Crate | Identifier | Metavariable | ScopedIdentifier | Self | Super | None = None

class SelfParameter(Node):
    __kind__ = 'self_parameter'
    __schema__ = None
    content: list[Lifetime | MutableSpecifier | Self]

class ShorthandFieldInitializer(Node):
    __kind__ = 'shorthand_field_initializer'
    __schema__ = None
    content: list[AttributeItem | Identifier]

class SlicePattern(Node):
    __kind__ = 'slice_pattern'
    __schema__ = None
    content: list[Pattern]

class SourceFile(Node):
    __kind__ = 'source_file'
    __schema__ = None
    content: list[DeclarationStatement | ExpressionStatement | Shebang]

class StaticItem(Node):
    __kind__ = 'static_item'
    __schema__ = None
    name: Identifier
    type: Type
    value: Expression | None = None
    content: list[MutableSpecifier | VisibilityModifier]

class StringLiteral(Node):
    __kind__ = 'string_literal'
    __schema__ = None
    content: list[EscapeSequence | StringContent]

class StructExpression(Node):
    __kind__ = 'struct_expression'
    __schema__ = None
    body: FieldInitializerList
    name: GenericTypeWithTurbofish | ScopedTypeIdentifier | TypeIdentifier

class StructItem(Node):
    __kind__ = 'struct_item'
    __schema__ = None
    body: FieldDeclarationList | OrderedFieldDeclarationList | None = None
    name: TypeIdentifier
    type_parameters: TypeParameters | None = None
    content: list[VisibilityModifier | WhereClause]

class StructPattern(Node):
    __kind__ = 'struct_pattern'
    __schema__ = None
    type: ScopedTypeIdentifier | TypeIdentifier
    content: list[FieldPattern | RemainingFieldPattern]

class TokenBindingPattern(Node):
    __kind__ = 'token_binding_pattern'
    __schema__ = None
    name: Metavariable
    type: FragmentSpecifier

class TokenRepetition(Node):
    __kind__ = 'token_repetition'
    __schema__ = None
    content: list[Literal | Crate | Identifier | Metavariable | MutableSpecifier | PrimitiveType | Self | Super | TokenRepetition | TokenTree]

class TokenRepetitionPattern(Node):
    __kind__ = 'token_repetition_pattern'
    __schema__ = None
    content: list[Literal | Crate | Identifier | Metavariable | MutableSpecifier | PrimitiveType | Self | Super | TokenBindingPattern | TokenRepetitionPattern | TokenTreePattern]

class TokenTree(Node):
    __kind__ = 'token_tree'
    __schema__ = None
    content: list[Literal | Crate | Identifier | Metavariable | MutableSpecifier | PrimitiveType | Self | Super | TokenRepetition | TokenTree]

class TokenTreePattern(Node):
    __kind__ = 'token_tree_pattern'
    __schema__ = None
    content: list[Literal | Crate | Identifier | Metavariable | MutableSpecifier | PrimitiveType | Self | Super | TokenBindingPattern | TokenRepetitionPattern | TokenTreePattern]

class TraitBounds(Node):
    __kind__ = 'trait_bounds'
    __schema__ = None
    content: list[Type | HigherRankedTraitBound | Lifetime]

class TraitItem(Node):
    __kind__ = 'trait_item'
    __schema__ = None
    body: DeclarationList
    bounds: TraitBounds | None = None
    name: TypeIdentifier
    type_parameters: TypeParameters | None = None
    content: list[VisibilityModifier | WhereClause]

class TryBlock(Node):
    __kind__ = 'try_block'
    __schema__ = None
    content: Block

class TryExpression(Node):
    __kind__ = 'try_expression'
    __schema__ = None
    content: Expression

class TupleExpression(Node):
    __kind__ = 'tuple_expression'
    __schema__ = None
    content: list[Expression | AttributeItem]

class TuplePattern(Node):
    __kind__ = 'tuple_pattern'
    __schema__ = None
    content: list[Pattern | ClosureExpression]

class TupleStructPattern(Node):
    __kind__ = 'tuple_struct_pattern'
    __schema__ = None
    type: GenericType | Identifier | ScopedIdentifier
    content: list[Pattern]

class TupleType(Node):
    __kind__ = 'tuple_type'
    __schema__ = None
    content: list[Type]

class TypeArguments(Node):
    __kind__ = 'type_arguments'
    __schema__ = None
    content: list[Literal | Type | Block | Lifetime | TraitBounds | TypeBinding]

class TypeBinding(Node):
    __kind__ = 'type_binding'
    __schema__ = None
    name: TypeIdentifier
    type: Type
    type_arguments: TypeArguments | None = None

class TypeCastExpression(Node):
    __kind__ = 'type_cast_expression'
    __schema__ = None
    type: Type
    value: Expression

class TypeItem(Node):
    __kind__ = 'type_item'
    __schema__ = None
    name: TypeIdentifier
    type: Type
    type_parameters: TypeParameters | None = None
    content: list[VisibilityModifier | WhereClause]

class TypeParameter(Node):
    __kind__ = 'type_parameter'
    __schema__ = None
    bounds: TraitBounds | None = None
    default_type: Type | None = None
    name: TypeIdentifier

class TypeParameters(Node):
    __kind__ = 'type_parameters'
    __schema__ = None
    content: list[AttributeItem | ConstParameter | LifetimeParameter | Metavariable | TypeParameter]

class UnaryExpression(Node):
    __kind__ = 'unary_expression'
    __schema__ = None
    content: Expression

class UnionItem(Node):
    __kind__ = 'union_item'
    __schema__ = None
    body: FieldDeclarationList
    name: TypeIdentifier
    type_parameters: TypeParameters | None = None
    content: list[VisibilityModifier | WhereClause]

class UnitExpression(Node):
    __kind__ = 'unit_expression'
    __schema__ = None

class UnitType(Node):
    __kind__ = 'unit_type'
    __schema__ = None

class UnsafeBlock(Node):
    __kind__ = 'unsafe_block'
    __schema__ = None
    content: Block

class UseAsClause(Node):
    __kind__ = 'use_as_clause'
    __schema__ = None
    alias: Identifier
    path: Crate | Identifier | Metavariable | ScopedIdentifier | Self | Super

class UseBounds(Node):
    __kind__ = 'use_bounds'
    __schema__ = None
    content: list[Lifetime | TypeIdentifier]

class UseDeclaration(Node):
    __kind__ = 'use_declaration'
    __schema__ = None
    argument: Crate | Identifier | Metavariable | ScopedIdentifier | ScopedUseList | Self | Super | UseAsClause | UseList | UseWildcard
    content: VisibilityModifier | None = None

class UseList(Node):
    __kind__ = 'use_list'
    __schema__ = None
    content: list[Crate | Identifier | Metavariable | ScopedIdentifier | ScopedUseList | Self | Super | UseAsClause | UseList | UseWildcard]

class UseWildcard(Node):
    __kind__ = 'use_wildcard'
    __schema__ = None
    content: Crate | Identifier | Metavariable | ScopedIdentifier | Self | Super | None = None

class VariadicParameter(Node):
    __kind__ = 'variadic_parameter'
    __schema__ = None
    pattern: Pattern | None = None
    content: MutableSpecifier | None = None

class VisibilityModifier(Node):
    __kind__ = 'visibility_modifier'
    __schema__ = None
    content: Crate | Identifier | Metavariable | ScopedIdentifier | Self | Super | None = None

class WhereClause(Node):
    __kind__ = 'where_clause'
    __schema__ = None
    content: list[WherePredicate]

class WherePredicate(Node):
    __kind__ = 'where_predicate'
    __schema__ = None
    bounds: TraitBounds
    left: ArrayType | GenericType | HigherRankedTraitBound | Lifetime | PointerType | PrimitiveType | ReferenceType | ScopedTypeIdentifier | TupleType | TypeIdentifier

class WhileExpression(Node):
    __kind__ = 'while_expression'
    __schema__ = None
    body: Block
    condition: Expression | LetChain | LetCondition
    content: Label | None = None

class YieldExpression(Node):
    __kind__ = 'yield_expression'
    __schema__ = None
    content: Expression | None = None

class CharLiteral(Node):
    __kind__ = 'char_literal'
    __schema__ = None

class Crate(Node):
    __kind__ = 'crate'
    __schema__ = None

class DocComment(Node):
    __kind__ = 'doc_comment'
    __schema__ = None

class EscapeSequence(Node):
    __kind__ = 'escape_sequence'
    __schema__ = None

class FieldIdentifier(Node):
    __kind__ = 'field_identifier'
    __schema__ = None

class FloatLiteral(Node):
    __kind__ = 'float_literal'
    __schema__ = None

class Identifier(Node):
    __kind__ = 'identifier'
    __schema__ = None

class IntegerLiteral(Node):
    __kind__ = 'integer_literal'
    __schema__ = None

class Metavariable(Node):
    __kind__ = 'metavariable'
    __schema__ = None

class MutableSpecifier(Node):
    __kind__ = 'mutable_specifier'
    __schema__ = None

class PrimitiveType(Node):
    __kind__ = 'primitive_type'
    __schema__ = None

class Self(Node):
    __kind__ = 'self'
    __schema__ = None

class Shebang(Node):
    __kind__ = 'shebang'
    __schema__ = None

class ShorthandFieldIdentifier(Node):
    __kind__ = 'shorthand_field_identifier'
    __schema__ = None

class StringContent(Node):
    __kind__ = 'string_content'
    __schema__ = None

class Super(Node):
    __kind__ = 'super'
    __schema__ = None

class TypeIdentifier(Node):
    __kind__ = 'type_identifier'
    __schema__ = None

DeclarationStatement = AssociatedType | AttributeItem | ConstItem | EmptyStatement | EnumItem | ExternCrateDeclaration | ForeignModItem | FunctionItem | FunctionSignatureItem | ImplItem | InnerAttributeItem | LetDeclaration | MacroDefinition | MacroInvocation | ModItem | StaticItem | StructItem | TraitItem | TypeItem | UnionItem | UseDeclaration

Literal = BooleanLiteral | CharLiteral | FloatLiteral | IntegerLiteral | RawStringLiteral | StringLiteral

LiteralPattern = BooleanLiteral | CharLiteral | FloatLiteral | IntegerLiteral | NegativeLiteral | RawStringLiteral | StringLiteral

Type = AbstractType | ArrayType | BoundedType | DynamicType | FunctionType | GenericType | MacroInvocation | Metavariable | NeverType | PointerType | PrimitiveType | ReferenceType | RemovedTraitBound | ScopedTypeIdentifier | TupleType | TypeIdentifier | UnitType

Expression = Literal | ArrayExpression | AssignmentExpression | AsyncBlock | AwaitExpression | BinaryExpression | Block | BreakExpression | CallExpression | ClosureExpression | CompoundAssignmentExpr | ConstBlock | ContinueExpression | FieldExpression | ForExpression | GenBlock | GenericFunction | Identifier | IfExpression | IndexExpression | LoopExpression | MacroInvocation | MatchExpression | Metavariable | ParenthesizedExpression | RangeExpression | ReferenceExpression | ReturnExpression | ScopedIdentifier | Self | StructExpression | TryBlock | TryExpression | TupleExpression | TypeCastExpression | UnaryExpression | UnitExpression | UnsafeBlock | WhileExpression | YieldExpression

Pattern = LiteralPattern | CapturedPattern | ConstBlock | GenericPattern | Identifier | MacroInvocation | MutPattern | OrPattern | RangePattern | RefPattern | ReferencePattern | RemainingFieldPattern | ScopedIdentifier | SlicePattern | StructPattern | TuplePattern | TupleStructPattern

KIND_MAP = {
    'abstract_type': AbstractType,
    'arguments': Arguments,
    'array_expression': ArrayExpression,
    'array_type': ArrayType,
    'assignment_expression': AssignmentExpression,
    'associated_type': AssociatedType,
    'async_block': AsyncBlock,
    'attribute': Attribute,
    'attribute_item': AttributeItem,
    'await_expression': AwaitExpression,
    'base_field_initializer': BaseFieldInitializer,
    'binary_expression': BinaryExpression,
    'block': Block,
    'block_comment': BlockComment,
    'boolean_literal': BooleanLiteral,
    'bounded_type': BoundedType,
    'bracketed_type': BracketedType,
    'break_expression': BreakExpression,
    'call_expression': CallExpression,
    'captured_pattern': CapturedPattern,
    'closure_expression': ClosureExpression,
    'closure_parameters': ClosureParameters,
    'compound_assignment_expr': CompoundAssignmentExpr,
    'const_block': ConstBlock,
    'const_item': ConstItem,
    'const_parameter': ConstParameter,
    'continue_expression': ContinueExpression,
    'declaration_list': DeclarationList,
    'dynamic_type': DynamicType,
    'else_clause': ElseClause,
    'empty_statement': EmptyStatement,
    'enum_item': EnumItem,
    'enum_variant': EnumVariant,
    'enum_variant_list': EnumVariantList,
    'expression_statement': ExpressionStatement,
    'extern_crate_declaration': ExternCrateDeclaration,
    'extern_modifier': ExternModifier,
    'field_declaration': FieldDeclaration,
    'field_declaration_list': FieldDeclarationList,
    'field_expression': FieldExpression,
    'field_initializer': FieldInitializer,
    'field_initializer_list': FieldInitializerList,
    'field_pattern': FieldPattern,
    'for_expression': ForExpression,
    'for_lifetimes': ForLifetimes,
    'foreign_mod_item': ForeignModItem,
    'fragment_specifier': FragmentSpecifier,
    'function_item': FunctionItem,
    'function_modifiers': FunctionModifiers,
    'function_signature_item': FunctionSignatureItem,
    'function_type': FunctionType,
    'gen_block': GenBlock,
    'generic_function': GenericFunction,
    'generic_pattern': GenericPattern,
    'generic_type': GenericType,
    'generic_type_with_turbofish': GenericTypeWithTurbofish,
    'higher_ranked_trait_bound': HigherRankedTraitBound,
    'if_expression': IfExpression,
    'impl_item': ImplItem,
    'index_expression': IndexExpression,
    'inner_attribute_item': InnerAttributeItem,
    'inner_doc_comment_marker': InnerDocCommentMarker,
    'label': Label,
    'let_chain': LetChain,
    'let_condition': LetCondition,
    'let_declaration': LetDeclaration,
    'lifetime': Lifetime,
    'lifetime_parameter': LifetimeParameter,
    'line_comment': LineComment,
    'loop_expression': LoopExpression,
    'macro_definition': MacroDefinition,
    'macro_invocation': MacroInvocation,
    'macro_rule': MacroRule,
    'match_arm': MatchArm,
    'match_block': MatchBlock,
    'match_expression': MatchExpression,
    'match_pattern': MatchPattern,
    'mod_item': ModItem,
    'mut_pattern': MutPattern,
    'negative_literal': NegativeLiteral,
    'never_type': NeverType,
    'or_pattern': OrPattern,
    'ordered_field_declaration_list': OrderedFieldDeclarationList,
    'outer_doc_comment_marker': OuterDocCommentMarker,
    'parameter': Parameter,
    'parameters': Parameters,
    'parenthesized_expression': ParenthesizedExpression,
    'pointer_type': PointerType,
    'qualified_type': QualifiedType,
    'range_expression': RangeExpression,
    'range_pattern': RangePattern,
    'raw_string_literal': RawStringLiteral,
    'ref_pattern': RefPattern,
    'reference_expression': ReferenceExpression,
    'reference_pattern': ReferencePattern,
    'reference_type': ReferenceType,
    'remaining_field_pattern': RemainingFieldPattern,
    'removed_trait_bound': RemovedTraitBound,
    'return_expression': ReturnExpression,
    'scoped_identifier': ScopedIdentifier,
    'scoped_type_identifier': ScopedTypeIdentifier,
    'scoped_use_list': ScopedUseList,
    'self_parameter': SelfParameter,
    'shorthand_field_initializer': ShorthandFieldInitializer,
    'slice_pattern': SlicePattern,
    'source_file': SourceFile,
    'static_item': StaticItem,
    'string_literal': StringLiteral,
    'struct_expression': StructExpression,
    'struct_item': StructItem,
    'struct_pattern': StructPattern,
    'token_binding_pattern': TokenBindingPattern,
    'token_repetition': TokenRepetition,
    'token_repetition_pattern': TokenRepetitionPattern,
    'token_tree': TokenTree,
    'token_tree_pattern': TokenTreePattern,
    'trait_bounds': TraitBounds,
    'trait_item': TraitItem,
    'try_block': TryBlock,
    'try_expression': TryExpression,
    'tuple_expression': TupleExpression,
    'tuple_pattern': TuplePattern,
    'tuple_struct_pattern': TupleStructPattern,
    'tuple_type': TupleType,
    'type_arguments': TypeArguments,
    'type_binding': TypeBinding,
    'type_cast_expression': TypeCastExpression,
    'type_item': TypeItem,
    'type_parameter': TypeParameter,
    'type_parameters': TypeParameters,
    'unary_expression': UnaryExpression,
    'union_item': UnionItem,
    'unit_expression': UnitExpression,
    'unit_type': UnitType,
    'unsafe_block': UnsafeBlock,
    'use_as_clause': UseAsClause,
    'use_bounds': UseBounds,
    'use_declaration': UseDeclaration,
    'use_list': UseList,
    'use_wildcard': UseWildcard,
    'variadic_parameter': VariadicParameter,
    'visibility_modifier': VisibilityModifier,
    'where_clause': WhereClause,
    'where_predicate': WherePredicate,
    'while_expression': WhileExpression,
    'yield_expression': YieldExpression,
    'char_literal': CharLiteral,
    'crate': Crate,
    'doc_comment': DocComment,
    'escape_sequence': EscapeSequence,
    'field_identifier': FieldIdentifier,
    'float_literal': FloatLiteral,
    'identifier': Identifier,
    'integer_literal': IntegerLiteral,
    'metavariable': Metavariable,
    'mutable_specifier': MutableSpecifier,
    'primitive_type': PrimitiveType,
    'self': Self,
    'shebang': Shebang,
    'shorthand_field_identifier': ShorthandFieldIdentifier,
    'string_content': StringContent,
    'super': Super,
    'type_identifier': TypeIdentifier,
}

for _node_class in KIND_MAP.values():
    _node_class.__schema__ = __schema__
    NodeMeta.rebuild(_node_class, globals())

grammar = Grammar._from_generated(__name__, '', __fingerprint__)
