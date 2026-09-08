"""Generated typed nodes; edit the schema or generator, not this file."""
from __future__ import annotations

from pydantree_sitter import Grammar, Node
from pydantree_sitter.nodes import NodeMeta
from pydantree_sitter.schema import NodeSchema

__schema__ = NodeSchema.from_list([{'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'atx_h1_marker'},
                         {'named': True, 'type': 'atx_h2_marker'},
                         {'named': True, 'type': 'atx_h3_marker'},
                         {'named': True, 'type': 'atx_h4_marker'},
                         {'named': True, 'type': 'atx_h5_marker'},
                         {'named': True, 'type': 'atx_h6_marker'},
                         {'named': True, 'type': 'block_continuation'}]},
  'extra': False,
  'fields': {'heading_content': {'multiple': False,
                                 'required': False,
                                 'types': [{'named': True, 'type': 'inline'}]}},
  'named': True,
  'root': False,
  'type': 'atx_heading'},
 {'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'backslash_escape'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'block_continuation'},
                         {'named': True, 'type': 'block_quote'},
                         {'named': True, 'type': 'block_quote_marker'},
                         {'named': True, 'type': 'fenced_code_block'},
                         {'named': True, 'type': 'html_block'},
                         {'named': True, 'type': 'indented_code_block'},
                         {'named': True, 'type': 'link_reference_definition'},
                         {'named': True, 'type': 'list'},
                         {'named': True, 'type': 'paragraph'},
                         {'named': True, 'type': 'pipe_table'},
                         {'named': True, 'type': 'section'},
                         {'named': True, 'type': 'setext_heading'},
                         {'named': True, 'type': 'thematic_break'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'block_quote'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'block_continuation'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'code_fence_content'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'minus_metadata'},
                         {'named': True, 'type': 'plus_metadata'},
                         {'named': True, 'type': 'section'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': True,
  'type': 'document'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'block_continuation'},
                         {'named': True, 'type': 'code_fence_content'},
                         {'named': True, 'type': 'fenced_code_block_delimiter'},
                         {'named': True, 'type': 'info_string'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'fenced_code_block'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'block_continuation'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'html_block'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'block_continuation'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'indented_code_block'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'backslash_escape'},
                         {'named': True, 'type': 'entity_reference'},
                         {'named': True, 'type': 'language'},
                         {'named': True, 'type': 'numeric_character_reference'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'info_string'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'block_continuation'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'inline'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'backslash_escape'},
                         {'named': True, 'type': 'entity_reference'},
                         {'named': True, 'type': 'numeric_character_reference'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'language'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'backslash_escape'},
                         {'named': True, 'type': 'entity_reference'},
                         {'named': True, 'type': 'numeric_character_reference'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'link_destination'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'backslash_escape'},
                         {'named': True, 'type': 'block_continuation'},
                         {'named': True, 'type': 'entity_reference'},
                         {'named': True, 'type': 'numeric_character_reference'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'link_label'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'block_continuation'},
                         {'named': True, 'type': 'link_destination'},
                         {'named': True, 'type': 'link_label'},
                         {'named': True, 'type': 'link_title'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'link_reference_definition'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'backslash_escape'},
                         {'named': True, 'type': 'block_continuation'},
                         {'named': True, 'type': 'entity_reference'},
                         {'named': True, 'type': 'numeric_character_reference'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'link_title'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'list_item'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'list'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'block_continuation'},
                         {'named': True, 'type': 'block_quote'},
                         {'named': True, 'type': 'fenced_code_block'},
                         {'named': True, 'type': 'html_block'},
                         {'named': True, 'type': 'indented_code_block'},
                         {'named': True, 'type': 'link_reference_definition'},
                         {'named': True, 'type': 'list'},
                         {'named': True, 'type': 'list_marker_dot'},
                         {'named': True, 'type': 'list_marker_minus'},
                         {'named': True, 'type': 'list_marker_parenthesis'},
                         {'named': True, 'type': 'list_marker_plus'},
                         {'named': True, 'type': 'list_marker_star'},
                         {'named': True, 'type': 'paragraph'},
                         {'named': True, 'type': 'pipe_table'},
                         {'named': True, 'type': 'section'},
                         {'named': True, 'type': 'setext_heading'},
                         {'named': True, 'type': 'task_list_marker_checked'},
                         {'named': True, 'type': 'task_list_marker_unchecked'},
                         {'named': True, 'type': 'thematic_break'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'list_item'},
 {'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'list_marker_dot'},
 {'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'list_marker_minus'},
 {'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'list_marker_parenthesis'},
 {'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'list_marker_plus'},
 {'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'list_marker_star'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'block_continuation'},
                         {'named': True, 'type': 'inline'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'paragraph'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'block_continuation'},
                         {'named': True, 'type': 'pipe_table_delimiter_row'},
                         {'named': True, 'type': 'pipe_table_header'},
                         {'named': True, 'type': 'pipe_table_row'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'pipe_table'},
 {'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'pipe_table_cell'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'pipe_table_align_left'},
                         {'named': True, 'type': 'pipe_table_align_right'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'pipe_table_delimiter_cell'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'pipe_table_delimiter_cell'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'pipe_table_delimiter_row'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'pipe_table_cell'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'pipe_table_header'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'pipe_table_cell'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'pipe_table_row'},
 {'children': {'multiple': True,
               'required': False,
               'types': [{'named': True, 'type': 'atx_heading'},
                         {'named': True, 'type': 'block_continuation'},
                         {'named': True, 'type': 'block_quote'},
                         {'named': True, 'type': 'fenced_code_block'},
                         {'named': True, 'type': 'html_block'},
                         {'named': True, 'type': 'indented_code_block'},
                         {'named': True, 'type': 'link_reference_definition'},
                         {'named': True, 'type': 'list'},
                         {'named': True, 'type': 'paragraph'},
                         {'named': True, 'type': 'pipe_table'},
                         {'named': True, 'type': 'section'},
                         {'named': True, 'type': 'setext_heading'},
                         {'named': True, 'type': 'thematic_break'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'section'},
 {'children': {'multiple': True,
               'required': True,
               'types': [{'named': True, 'type': 'block_continuation'},
                         {'named': True, 'type': 'setext_h1_underline'},
                         {'named': True, 'type': 'setext_h2_underline'}]},
  'extra': False,
  'fields': {'heading_content': {'multiple': False,
                                 'required': True,
                                 'types': [{'named': True, 'type': 'paragraph'}]}},
  'named': True,
  'root': False,
  'type': 'setext_heading'},
 {'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'task_list_marker_checked'},
 {'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'task_list_marker_unchecked'},
 {'children': {'multiple': False,
               'required': False,
               'types': [{'named': True, 'type': 'block_continuation'}]},
  'extra': False,
  'fields': {},
  'named': True,
  'root': False,
  'type': 'thematic_break'},
 {'extra': False, 'named': False, 'root': False, 'type': '!'},
 {'extra': False, 'named': False, 'root': False, 'type': '"'},
 {'extra': False, 'named': False, 'root': False, 'type': '#'},
 {'extra': False, 'named': False, 'root': False, 'type': '$'},
 {'extra': False, 'named': False, 'root': False, 'type': '%'},
 {'extra': False, 'named': False, 'root': False, 'type': '&'},
 {'extra': False, 'named': False, 'root': False, 'type': "'"},
 {'extra': False, 'named': False, 'root': False, 'type': '('},
 {'extra': False, 'named': False, 'root': False, 'type': ')'},
 {'extra': False, 'named': False, 'root': False, 'type': '*'},
 {'extra': False, 'named': False, 'root': False, 'type': '+'},
 {'extra': False, 'named': False, 'root': False, 'type': ','},
 {'extra': False, 'named': False, 'root': False, 'type': '-'},
 {'extra': False, 'named': False, 'root': False, 'type': '-->'},
 {'extra': False, 'named': False, 'root': False, 'type': '.'},
 {'extra': False, 'named': False, 'root': False, 'type': '/'},
 {'extra': False, 'named': False, 'root': False, 'type': ':'},
 {'extra': False, 'named': False, 'root': False, 'type': ';'},
 {'extra': False, 'named': False, 'root': False, 'type': '<'},
 {'extra': False, 'named': False, 'root': False, 'type': '='},
 {'extra': False, 'named': False, 'root': False, 'type': '>'},
 {'extra': False, 'named': False, 'root': False, 'type': '?'},
 {'extra': False, 'named': False, 'root': False, 'type': '?>'},
 {'extra': False, 'named': False, 'root': False, 'type': '@'},
 {'extra': False, 'named': False, 'root': False, 'type': '['},
 {'extra': False, 'named': False, 'root': False, 'type': '\\'},
 {'extra': False, 'named': False, 'root': False, 'type': ']'},
 {'extra': False, 'named': False, 'root': False, 'type': ']]>'},
 {'extra': False, 'named': False, 'root': False, 'type': '^'},
 {'extra': False, 'named': False, 'root': False, 'type': '_'},
 {'extra': False, 'named': False, 'root': False, 'type': '`'},
 {'extra': False, 'named': True, 'root': False, 'type': 'atx_h1_marker'},
 {'extra': False, 'named': True, 'root': False, 'type': 'atx_h2_marker'},
 {'extra': False, 'named': True, 'root': False, 'type': 'atx_h3_marker'},
 {'extra': False, 'named': True, 'root': False, 'type': 'atx_h4_marker'},
 {'extra': False, 'named': True, 'root': False, 'type': 'atx_h5_marker'},
 {'extra': False, 'named': True, 'root': False, 'type': 'atx_h6_marker'},
 {'extra': False, 'named': True, 'root': False, 'type': 'block_continuation'},
 {'extra': False, 'named': True, 'root': False, 'type': 'block_quote_marker'},
 {'extra': False, 'named': True, 'root': False, 'type': 'entity_reference'},
 {'extra': False, 'named': True, 'root': False, 'type': 'fenced_code_block_delimiter'},
 {'extra': False, 'named': True, 'root': False, 'type': 'minus_metadata'},
 {'extra': False, 'named': True, 'root': False, 'type': 'numeric_character_reference'},
 {'extra': False, 'named': True, 'root': False, 'type': 'pipe_table_align_left'},
 {'extra': False, 'named': True, 'root': False, 'type': 'pipe_table_align_right'},
 {'extra': False, 'named': True, 'root': False, 'type': 'plus_metadata'},
 {'extra': False, 'named': True, 'root': False, 'type': 'setext_h1_underline'},
 {'extra': False, 'named': True, 'root': False, 'type': 'setext_h2_underline'},
 {'extra': False, 'named': False, 'root': False, 'type': '{'},
 {'extra': False, 'named': False, 'root': False, 'type': '|'},
 {'extra': False, 'named': False, 'root': False, 'type': '}'},
 {'extra': False, 'named': False, 'root': False, 'type': '~'}])
__fingerprint__ = ('markdown',
 15,
 (0, 1, 0),
 ('end',
  '_backslash_escape',
  'entity_reference',
  'numeric_character_reference',
  '[',
  ']',
  '<',
  '>',
  '!',
  '"',
  '#',
  '$',
  '%',
  '&',
  "'",
  '*',
  '+',
  ',',
  '-',
  '.',
  '/',
  ':',
  ';',
  '=',
  '?',
  '@',
  '\\',
  '^',
  '_',
  '`',
  '{',
  '|',
  '}',
  '~',
  '(',
  ')',
  '-->',
  '?>',
  ']]>',
  '_word_token1',
  '_word_token2',
  '_word_token3',
  '_whitespace',
  '_line_ending',
  '_soft_line_ending',
  '_block_close',
  'block_continuation',
  'block_quote_marker',
  '_indented_chunk_start',
  'atx_h1_marker',
  'atx_h2_marker',
  'atx_h3_marker',
  'atx_h4_marker',
  'atx_h5_marker',
  'atx_h6_marker',
  'setext_h1_underline',
  'setext_h2_underline',
  '_thematic_break',
  '_list_marker_minus',
  '_list_marker_plus',
  '_list_marker_star',
  '_list_marker_parenthesis',
  '_list_marker_dot',
  '_list_marker_minus_dont_interrupt',
  '_list_marker_plus_dont_interrupt',
  '_list_marker_star_dont_interrupt',
  '_list_marker_parenthesis_dont_interrupt',
  '_list_marker_dot_dont_interrupt',
  'fenced_code_block_delimiter',
  'fenced_code_block_delimiter',
  '_blank_line_start',
  'fenced_code_block_delimiter',
  'fenced_code_block_delimiter',
  '_html_block_1_start',
  '_html_block_1_end',
  '_html_block_2_start',
  '_html_block_3_start',
  '_html_block_4_start',
  '_html_block_5_start',
  '_html_block_6_start',
  '_html_block_7_start',
  '_close_block',
  '_no_indented_chunk',
  '_error',
  '_trigger_error',
  '_eof',
  'minus_metadata',
  'plus_metadata',
  '_pipe_table_start',
  '_pipe_table_line_ending',
  'document',
  'backslash_escape',
  'link_label',
  'link_destination',
  '_link_destination_parenthesis',
  '_text_no_angle',
  'link_title',
  '_last_token_punctuation',
  '_block',
  '_block_not_section',
  'section',
  '_section1',
  '_section2',
  '_section3',
  '_section4',
  '_section5',
  '_section6',
  'thematic_break',
  'atx_heading',
  'atx_heading',
  'atx_heading',
  'atx_heading',
  'atx_heading',
  'atx_heading',
  '_atx_heading_content',
  'setext_heading',
  'setext_heading',
  'indented_code_block',
  '_indented_chunk',
  'fenced_code_block',
  'code_fence_content',
  'info_string',
  'language',
  'html_block',
  '_html_block_1',
  '_html_block_2',
  '_html_block_3',
  '_html_block_4',
  '_html_block_5',
  '_html_block_6',
  '_html_block_7',
  'link_reference_definition',
  '_text_inline_no_link',
  'paragraph',
  '_blank_line',
  'block_quote',
  'list',
  '_list_plus',
  '_list_minus',
  '_list_star',
  '_list_dot',
  '_list_parenthesis',
  'list_marker_plus',
  'list_marker_minus',
  'list_marker_star',
  'list_marker_dot',
  'list_marker_parenthesis',
  'list_item',
  'list_item',
  'list_item',
  'list_item',
  'list_item',
  '_list_item_content',
  '_newline',
  '_soft_line_break',
  '_line',
  '_word',
  'task_list_marker_checked',
  'task_list_marker_unchecked',
  'pipe_table',
  '_pipe_table_newline',
  'pipe_table_delimiter_row',
  'pipe_table_delimiter_cell',
  'pipe_table_row',
  'pipe_table_cell',
  'document_repeat1',
  'document_repeat2',
  'link_label_repeat1',
  'link_destination_repeat1',
  'link_destination_repeat2',
  'link_title_repeat1',
  'link_title_repeat2',
  'link_title_repeat3',
  '_section1_repeat1',
  '_section2_repeat1',
  '_section3_repeat1',
  '_section4_repeat1',
  '_section5_repeat1',
  'indented_code_block_repeat1',
  '_indented_chunk_repeat1',
  'code_fence_content_repeat1',
  'info_string_repeat1',
  'info_string_repeat2',
  'language_repeat1',
  '_html_block_1_repeat1',
  '_html_block_2_repeat1',
  '_html_block_3_repeat1',
  '_html_block_4_repeat1',
  '_html_block_5_repeat1',
  '_html_block_6_repeat1',
  'paragraph_repeat1',
  'block_quote_repeat1',
  '_list_plus_repeat1',
  '_list_minus_repeat1',
  '_list_star_repeat1',
  '_list_dot_repeat1',
  '_list_parenthesis_repeat1',
  '_line_repeat1',
  'pipe_table_repeat1',
  'pipe_table_delimiter_row_repeat1',
  'pipe_table_delimiter_cell_repeat1',
  'pipe_table_row_repeat1',
  'pipe_table_cell_repeat1',
  'inline',
  'pipe_table_align_left',
  'pipe_table_align_right',
  'pipe_table_header'),
 ('heading_content',))

class AtxHeading(Node):
    __kind__ = 'atx_heading'
    __schema__ = None
    heading_content: Inline | None = None
    content: list[AtxH1Marker | AtxH2Marker | AtxH3Marker | AtxH4Marker | AtxH5Marker | AtxH6Marker | BlockContinuation]

class BackslashEscape(Node):
    __kind__ = 'backslash_escape'
    __schema__ = None

class BlockQuote(Node):
    __kind__ = 'block_quote'
    __schema__ = None
    content: list[BlockContinuation | BlockQuote | BlockQuoteMarker | FencedCodeBlock | HtmlBlock | IndentedCodeBlock | LinkReferenceDefinition | List | Paragraph | PipeTable | Section | SetextHeading | ThematicBreak]

class CodeFenceContent(Node):
    __kind__ = 'code_fence_content'
    __schema__ = None
    content: list[BlockContinuation]

class Document(Node):
    __kind__ = 'document'
    __schema__ = None
    content: list[MinusMetadata | PlusMetadata | Section]

class FencedCodeBlock(Node):
    __kind__ = 'fenced_code_block'
    __schema__ = None
    content: list[BlockContinuation | CodeFenceContent | FencedCodeBlockDelimiter | InfoString]

class HtmlBlock(Node):
    __kind__ = 'html_block'
    __schema__ = None
    content: list[BlockContinuation]

class IndentedCodeBlock(Node):
    __kind__ = 'indented_code_block'
    __schema__ = None
    content: list[BlockContinuation]

class InfoString(Node):
    __kind__ = 'info_string'
    __schema__ = None
    content: list[BackslashEscape | EntityReference | Language | NumericCharacterReference]

class Inline(Node):
    __kind__ = 'inline'
    __schema__ = None
    content: list[BlockContinuation]

class Language(Node):
    __kind__ = 'language'
    __schema__ = None
    content: list[BackslashEscape | EntityReference | NumericCharacterReference]

class LinkDestination(Node):
    __kind__ = 'link_destination'
    __schema__ = None
    content: list[BackslashEscape | EntityReference | NumericCharacterReference]

class LinkLabel(Node):
    __kind__ = 'link_label'
    __schema__ = None
    content: list[BackslashEscape | BlockContinuation | EntityReference | NumericCharacterReference]

class LinkReferenceDefinition(Node):
    __kind__ = 'link_reference_definition'
    __schema__ = None
    content: list[BlockContinuation | LinkDestination | LinkLabel | LinkTitle]

class LinkTitle(Node):
    __kind__ = 'link_title'
    __schema__ = None
    content: list[BackslashEscape | BlockContinuation | EntityReference | NumericCharacterReference]

class List(Node):
    __kind__ = 'list'
    __schema__ = None
    content: list[ListItem]

class ListItem(Node):
    __kind__ = 'list_item'
    __schema__ = None
    content: list[BlockContinuation | BlockQuote | FencedCodeBlock | HtmlBlock | IndentedCodeBlock | LinkReferenceDefinition | List | ListMarkerDot | ListMarkerMinus | ListMarkerParenthesis | ListMarkerPlus | ListMarkerStar | Paragraph | PipeTable | Section | SetextHeading | TaskListMarkerChecked | TaskListMarkerUnchecked | ThematicBreak]

class ListMarkerDot(Node):
    __kind__ = 'list_marker_dot'
    __schema__ = None

class ListMarkerMinus(Node):
    __kind__ = 'list_marker_minus'
    __schema__ = None

class ListMarkerParenthesis(Node):
    __kind__ = 'list_marker_parenthesis'
    __schema__ = None

class ListMarkerPlus(Node):
    __kind__ = 'list_marker_plus'
    __schema__ = None

class ListMarkerStar(Node):
    __kind__ = 'list_marker_star'
    __schema__ = None

class Paragraph(Node):
    __kind__ = 'paragraph'
    __schema__ = None
    content: list[BlockContinuation | Inline]

class PipeTable(Node):
    __kind__ = 'pipe_table'
    __schema__ = None
    content: list[BlockContinuation | PipeTableDelimiterRow | PipeTableHeader | PipeTableRow]

class PipeTableCell(Node):
    __kind__ = 'pipe_table_cell'
    __schema__ = None

class PipeTableDelimiterCell(Node):
    __kind__ = 'pipe_table_delimiter_cell'
    __schema__ = None
    content: list[PipeTableAlignLeft | PipeTableAlignRight]

class PipeTableDelimiterRow(Node):
    __kind__ = 'pipe_table_delimiter_row'
    __schema__ = None
    content: list[PipeTableDelimiterCell]

class PipeTableHeader(Node):
    __kind__ = 'pipe_table_header'
    __schema__ = None
    content: list[PipeTableCell]

class PipeTableRow(Node):
    __kind__ = 'pipe_table_row'
    __schema__ = None
    content: list[PipeTableCell]

class Section(Node):
    __kind__ = 'section'
    __schema__ = None
    content: list[AtxHeading | BlockContinuation | BlockQuote | FencedCodeBlock | HtmlBlock | IndentedCodeBlock | LinkReferenceDefinition | List | Paragraph | PipeTable | Section | SetextHeading | ThematicBreak]

class SetextHeading(Node):
    __kind__ = 'setext_heading'
    __schema__ = None
    heading_content: Paragraph
    content: list[BlockContinuation | SetextH1Underline | SetextH2Underline]

class TaskListMarkerChecked(Node):
    __kind__ = 'task_list_marker_checked'
    __schema__ = None

class TaskListMarkerUnchecked(Node):
    __kind__ = 'task_list_marker_unchecked'
    __schema__ = None

class ThematicBreak(Node):
    __kind__ = 'thematic_break'
    __schema__ = None
    content: BlockContinuation | None = None

class AtxH1Marker(Node):
    __kind__ = 'atx_h1_marker'
    __schema__ = None

class AtxH2Marker(Node):
    __kind__ = 'atx_h2_marker'
    __schema__ = None

class AtxH3Marker(Node):
    __kind__ = 'atx_h3_marker'
    __schema__ = None

class AtxH4Marker(Node):
    __kind__ = 'atx_h4_marker'
    __schema__ = None

class AtxH5Marker(Node):
    __kind__ = 'atx_h5_marker'
    __schema__ = None

class AtxH6Marker(Node):
    __kind__ = 'atx_h6_marker'
    __schema__ = None

class BlockContinuation(Node):
    __kind__ = 'block_continuation'
    __schema__ = None

class BlockQuoteMarker(Node):
    __kind__ = 'block_quote_marker'
    __schema__ = None

class EntityReference(Node):
    __kind__ = 'entity_reference'
    __schema__ = None

class FencedCodeBlockDelimiter(Node):
    __kind__ = 'fenced_code_block_delimiter'
    __schema__ = None

class MinusMetadata(Node):
    __kind__ = 'minus_metadata'
    __schema__ = None

class NumericCharacterReference(Node):
    __kind__ = 'numeric_character_reference'
    __schema__ = None

class PipeTableAlignLeft(Node):
    __kind__ = 'pipe_table_align_left'
    __schema__ = None

class PipeTableAlignRight(Node):
    __kind__ = 'pipe_table_align_right'
    __schema__ = None

class PlusMetadata(Node):
    __kind__ = 'plus_metadata'
    __schema__ = None

class SetextH1Underline(Node):
    __kind__ = 'setext_h1_underline'
    __schema__ = None

class SetextH2Underline(Node):
    __kind__ = 'setext_h2_underline'
    __schema__ = None

KIND_MAP = {
    'atx_heading': AtxHeading,
    'backslash_escape': BackslashEscape,
    'block_quote': BlockQuote,
    'code_fence_content': CodeFenceContent,
    'document': Document,
    'fenced_code_block': FencedCodeBlock,
    'html_block': HtmlBlock,
    'indented_code_block': IndentedCodeBlock,
    'info_string': InfoString,
    'inline': Inline,
    'language': Language,
    'link_destination': LinkDestination,
    'link_label': LinkLabel,
    'link_reference_definition': LinkReferenceDefinition,
    'link_title': LinkTitle,
    'list': List,
    'list_item': ListItem,
    'list_marker_dot': ListMarkerDot,
    'list_marker_minus': ListMarkerMinus,
    'list_marker_parenthesis': ListMarkerParenthesis,
    'list_marker_plus': ListMarkerPlus,
    'list_marker_star': ListMarkerStar,
    'paragraph': Paragraph,
    'pipe_table': PipeTable,
    'pipe_table_cell': PipeTableCell,
    'pipe_table_delimiter_cell': PipeTableDelimiterCell,
    'pipe_table_delimiter_row': PipeTableDelimiterRow,
    'pipe_table_header': PipeTableHeader,
    'pipe_table_row': PipeTableRow,
    'section': Section,
    'setext_heading': SetextHeading,
    'task_list_marker_checked': TaskListMarkerChecked,
    'task_list_marker_unchecked': TaskListMarkerUnchecked,
    'thematic_break': ThematicBreak,
    'atx_h1_marker': AtxH1Marker,
    'atx_h2_marker': AtxH2Marker,
    'atx_h3_marker': AtxH3Marker,
    'atx_h4_marker': AtxH4Marker,
    'atx_h5_marker': AtxH5Marker,
    'atx_h6_marker': AtxH6Marker,
    'block_continuation': BlockContinuation,
    'block_quote_marker': BlockQuoteMarker,
    'entity_reference': EntityReference,
    'fenced_code_block_delimiter': FencedCodeBlockDelimiter,
    'minus_metadata': MinusMetadata,
    'numeric_character_reference': NumericCharacterReference,
    'pipe_table_align_left': PipeTableAlignLeft,
    'pipe_table_align_right': PipeTableAlignRight,
    'plus_metadata': PlusMetadata,
    'setext_h1_underline': SetextH1Underline,
    'setext_h2_underline': SetextH2Underline,
}

for _node_class in KIND_MAP.values():
    _node_class.__schema__ = __schema__
    NodeMeta.rebuild(_node_class, globals())

grammar = Grammar._from_generated(__name__, '', __fingerprint__)
