from __future__ import annotations
from pydantree.core import TSNode

NODE_MAP: dict[str, type[TSNode]] = {}

class CompoundStatementNode(TSNode):
    pass

NODE_MAP['_compound_statement'] = CompoundStatementNode

class SimpleStatementNode(TSNode):
    pass

NODE_MAP['_simple_statement'] = SimpleStatementNode

class ExpressionNode(TSNode):
    pass

NODE_MAP['expression'] = ExpressionNode

class ParameterNode(TSNode):
    pass

NODE_MAP['parameter'] = ParameterNode

class PatternNode(TSNode):
    pass

NODE_MAP['pattern'] = PatternNode

class PrimaryExpressionNode(TSNode):
    pass

NODE_MAP['primary_expression'] = PrimaryExpressionNode

class AliasedImportNode(TSNode):
    __match_args__ = ('type_name', 'alias', 'name')
    pass

NODE_MAP['aliased_import'] = AliasedImportNode

class ArgumentListNode(TSNode):
    pass

NODE_MAP['argument_list'] = ArgumentListNode

class AsPatternNode(TSNode):
    __match_args__ = ('type_name', 'alias')
    pass

NODE_MAP['as_pattern'] = AsPatternNode

class AssertStatementNode(TSNode):
    pass

NODE_MAP['assert_statement'] = AssertStatementNode

class AssignmentNode(TSNode):
    __match_args__ = ('type_name', 'left', 'right', 'type')
    pass

NODE_MAP['assignment'] = AssignmentNode

class AttributeNode(TSNode):
    __match_args__ = ('type_name', 'attribute', 'object')
    pass

NODE_MAP['attribute'] = AttributeNode

class AugmentedAssignmentNode(TSNode):
    __match_args__ = ('type_name', 'left', 'operator', 'right')
    pass

NODE_MAP['augmented_assignment'] = AugmentedAssignmentNode

class AwaitExpressionNode(TSNode):
    pass

NODE_MAP['await'] = AwaitExpressionNode

class BinaryOperatorNode(TSNode):
    __match_args__ = ('type_name', 'left', 'operator', 'right')
    pass

NODE_MAP['binary_operator'] = BinaryOperatorNode

class BlockNode(TSNode):
    __match_args__ = ('type_name', 'alternative')
    pass

NODE_MAP['block'] = BlockNode

class BooleanOperatorNode(TSNode):
    __match_args__ = ('type_name', 'left', 'operator', 'right')
    pass

NODE_MAP['boolean_operator'] = BooleanOperatorNode

class BreakStatementNode(TSNode):
    pass

NODE_MAP['break_statement'] = BreakStatementNode

class CallNode(TSNode):
    __match_args__ = ('type_name', 'arguments', 'function')
    pass

NODE_MAP['call'] = CallNode

class CaseClauseNode(TSNode):
    __match_args__ = ('type_name', 'consequence', 'guard')
    pass

NODE_MAP['case_clause'] = CaseClauseNode

class CasePatternNode(TSNode):
    pass

NODE_MAP['case_pattern'] = CasePatternNode

class ChevronNode(TSNode):
    pass

NODE_MAP['chevron'] = ChevronNode

class ClassDefinitionNode(TSNode):
    __match_args__ = ('type_name', 'body', 'name', 'superclasses', 'type_parameters')
    pass

NODE_MAP['class_definition'] = ClassDefinitionNode

class ClassPatternNode(TSNode):
    pass

NODE_MAP['class_pattern'] = ClassPatternNode

class ComparisonOperatorNode(TSNode):
    __match_args__ = ('type_name', 'operators')
    pass

NODE_MAP['comparison_operator'] = ComparisonOperatorNode

class ComplexPatternNode(TSNode):
    pass

NODE_MAP['complex_pattern'] = ComplexPatternNode

class ConcatenatedStringNode(TSNode):
    pass

NODE_MAP['concatenated_string'] = ConcatenatedStringNode

class ConditionalExpressionNode(TSNode):
    pass

NODE_MAP['conditional_expression'] = ConditionalExpressionNode

class ConstrainedTypeNode(TSNode):
    pass

NODE_MAP['constrained_type'] = ConstrainedTypeNode

class ContinueStatementNode(TSNode):
    pass

NODE_MAP['continue_statement'] = ContinueStatementNode

class DecoratedDefinitionNode(TSNode):
    __match_args__ = ('type_name', 'definition')
    pass

NODE_MAP['decorated_definition'] = DecoratedDefinitionNode

class DecoratorNode(TSNode):
    pass

NODE_MAP['decorator'] = DecoratorNode

class DefaultParameterNode(TSNode):
    __match_args__ = ('type_name', 'name', 'value')
    pass

NODE_MAP['default_parameter'] = DefaultParameterNode

class DeleteStatementNode(TSNode):
    pass

NODE_MAP['delete_statement'] = DeleteStatementNode

class DictPatternNode(TSNode):
    __match_args__ = ('type_name', 'key', 'value')
    pass

NODE_MAP['dict_pattern'] = DictPatternNode

class DictionaryNode(TSNode):
    pass

NODE_MAP['dictionary'] = DictionaryNode

class DictionaryComprehensionNode(TSNode):
    __match_args__ = ('type_name', 'body')
    pass

NODE_MAP['dictionary_comprehension'] = DictionaryComprehensionNode

class DictionarySplatNode(TSNode):
    pass

NODE_MAP['dictionary_splat'] = DictionarySplatNode

class DictionarySplatPatternNode(TSNode):
    pass

NODE_MAP['dictionary_splat_pattern'] = DictionarySplatPatternNode

class DottedNameNode(TSNode):
    pass

NODE_MAP['dotted_name'] = DottedNameNode

class ElifClauseNode(TSNode):
    __match_args__ = ('type_name', 'condition', 'consequence')
    pass

NODE_MAP['elif_clause'] = ElifClauseNode

class ElseClauseNode(TSNode):
    __match_args__ = ('type_name', 'body')
    pass

NODE_MAP['else_clause'] = ElseClauseNode

class ExceptClauseNode(TSNode):
    pass

NODE_MAP['except_clause'] = ExceptClauseNode

class ExceptGroupClauseNode(TSNode):
    pass

NODE_MAP['except_group_clause'] = ExceptGroupClauseNode

class ExecStatementNode(TSNode):
    __match_args__ = ('type_name', 'code')
    pass

NODE_MAP['exec_statement'] = ExecStatementNode

class ExpressionListNode(TSNode):
    pass

NODE_MAP['expression_list'] = ExpressionListNode

class ExpressionStatementNode(TSNode):
    pass

NODE_MAP['expression_statement'] = ExpressionStatementNode

class FinallyClauseNode(TSNode):
    pass

NODE_MAP['finally_clause'] = FinallyClauseNode

class ForInClauseNode(TSNode):
    __match_args__ = ('type_name', 'left', 'right')
    pass

NODE_MAP['for_in_clause'] = ForInClauseNode

class ForStatementNode(TSNode):
    __match_args__ = ('type_name', 'alternative', 'body', 'left', 'right')
    pass

NODE_MAP['for_statement'] = ForStatementNode

class FormatExpressionNode(TSNode):
    __match_args__ = ('type_name', 'expression', 'format_specifier', 'type_conversion')
    pass

NODE_MAP['format_expression'] = FormatExpressionNode

class FormatSpecifierNode(TSNode):
    pass

NODE_MAP['format_specifier'] = FormatSpecifierNode

class FunctionDefinitionNode(TSNode):
    __match_args__ = ('type_name', 'body', 'name', 'parameters', 'return_type', 'type_parameters')
    pass

NODE_MAP['function_definition'] = FunctionDefinitionNode

class FutureImportStatementNode(TSNode):
    __match_args__ = ('type_name', 'name')
    pass

NODE_MAP['future_import_statement'] = FutureImportStatementNode

class GeneratorExpressionNode(TSNode):
    __match_args__ = ('type_name', 'body')
    pass

NODE_MAP['generator_expression'] = GeneratorExpressionNode

class GenericTypeNode(TSNode):
    pass

NODE_MAP['generic_type'] = GenericTypeNode

class GlobalStatementNode(TSNode):
    pass

NODE_MAP['global_statement'] = GlobalStatementNode

class IfClauseNode(TSNode):
    pass

NODE_MAP['if_clause'] = IfClauseNode

class IfStatementNode(TSNode):
    __match_args__ = ('type_name', 'alternative', 'condition', 'consequence')
    pass

NODE_MAP['if_statement'] = IfStatementNode

class ImportFromStatementNode(TSNode):
    __match_args__ = ('type_name', 'module_name', 'name')
    pass

NODE_MAP['import_from_statement'] = ImportFromStatementNode

class ImportPrefixNode(TSNode):
    pass

NODE_MAP['import_prefix'] = ImportPrefixNode

class ImportStatementNode(TSNode):
    __match_args__ = ('type_name', 'name')
    pass

NODE_MAP['import_statement'] = ImportStatementNode

class InterpolationNode(TSNode):
    __match_args__ = ('type_name', 'expression', 'format_specifier', 'type_conversion')
    pass

NODE_MAP['interpolation'] = InterpolationNode

class KeywordArgumentNode(TSNode):
    __match_args__ = ('type_name', 'name', 'value')
    pass

NODE_MAP['keyword_argument'] = KeywordArgumentNode

class KeywordPatternNode(TSNode):
    pass

NODE_MAP['keyword_pattern'] = KeywordPatternNode

class KeywordSeparatorNode(TSNode):
    pass

NODE_MAP['keyword_separator'] = KeywordSeparatorNode

class LambdaFunctionNode(TSNode):
    __match_args__ = ('type_name', 'body', 'parameters')
    pass

NODE_MAP['lambda'] = LambdaFunctionNode

class LambdaParametersNode(TSNode):
    pass

NODE_MAP['lambda_parameters'] = LambdaParametersNode

class ListNode(TSNode):
    pass

NODE_MAP['list'] = ListNode

class ListComprehensionNode(TSNode):
    __match_args__ = ('type_name', 'body')
    pass

NODE_MAP['list_comprehension'] = ListComprehensionNode

class ListPatternNode(TSNode):
    pass

NODE_MAP['list_pattern'] = ListPatternNode

class ListSplatNode(TSNode):
    pass

NODE_MAP['list_splat'] = ListSplatNode

class ListSplatPatternNode(TSNode):
    pass

NODE_MAP['list_splat_pattern'] = ListSplatPatternNode

class MatchStatementNode(TSNode):
    __match_args__ = ('type_name', 'body', 'subject')
    pass

NODE_MAP['match_statement'] = MatchStatementNode

class MemberTypeNode(TSNode):
    pass

NODE_MAP['member_type'] = MemberTypeNode

class ModuleNode(TSNode):
    pass

NODE_MAP['module'] = ModuleNode

class NamedExpressionNode(TSNode):
    __match_args__ = ('type_name', 'name', 'value')
    pass

NODE_MAP['named_expression'] = NamedExpressionNode

class NonlocalStatementNode(TSNode):
    pass

NODE_MAP['nonlocal_statement'] = NonlocalStatementNode

class NotOperatorNode(TSNode):
    __match_args__ = ('type_name', 'argument')
    pass

NODE_MAP['not_operator'] = NotOperatorNode

class PairNode(TSNode):
    __match_args__ = ('type_name', 'key', 'value')
    pass

NODE_MAP['pair'] = PairNode

class ParametersNode(TSNode):
    pass

NODE_MAP['parameters'] = ParametersNode

class ParenthesizedExpressionNode(TSNode):
    pass

NODE_MAP['parenthesized_expression'] = ParenthesizedExpressionNode

class ParenthesizedListSplatNode(TSNode):
    pass

NODE_MAP['parenthesized_list_splat'] = ParenthesizedListSplatNode

class PassStatementNode(TSNode):
    pass

NODE_MAP['pass_statement'] = PassStatementNode

class PatternListNode(TSNode):
    pass

NODE_MAP['pattern_list'] = PatternListNode

class PositionalSeparatorNode(TSNode):
    pass

NODE_MAP['positional_separator'] = PositionalSeparatorNode

class PrintStatementNode(TSNode):
    __match_args__ = ('type_name', 'argument')
    pass

NODE_MAP['print_statement'] = PrintStatementNode

class RaiseStatementNode(TSNode):
    __match_args__ = ('type_name', 'cause')
    pass

NODE_MAP['raise_statement'] = RaiseStatementNode

class RelativeImportNode(TSNode):
    pass

NODE_MAP['relative_import'] = RelativeImportNode

class ReturnStatementNode(TSNode):
    pass

NODE_MAP['return_statement'] = ReturnStatementNode

class SetNode(TSNode):
    pass

NODE_MAP['set'] = SetNode

class SetComprehensionNode(TSNode):
    __match_args__ = ('type_name', 'body')
    pass

NODE_MAP['set_comprehension'] = SetComprehensionNode

class SliceNode(TSNode):
    pass

NODE_MAP['slice'] = SliceNode

class SplatPatternNode(TSNode):
    pass

NODE_MAP['splat_pattern'] = SplatPatternNode

class SplatTypeNode(TSNode):
    pass

NODE_MAP['splat_type'] = SplatTypeNode

class StringNode(TSNode):
    pass

NODE_MAP['string'] = StringNode

class StringContentNode(TSNode):
    pass

NODE_MAP['string_content'] = StringContentNode

class SubscriptNode(TSNode):
    __match_args__ = ('type_name', 'subscript', 'value')
    pass

NODE_MAP['subscript'] = SubscriptNode

class TryStatementNode(TSNode):
    __match_args__ = ('type_name', 'body')
    pass

NODE_MAP['try_statement'] = TryStatementNode

class TupleNode(TSNode):
    pass

NODE_MAP['tuple'] = TupleNode

class TuplePatternNode(TSNode):
    pass

NODE_MAP['tuple_pattern'] = TuplePatternNode

class TypeAliasNode(TSNode):
    pass

NODE_MAP['type'] = TypeAliasNode

class TypeAliasStatementNode(TSNode):
    pass

NODE_MAP['type_alias_statement'] = TypeAliasStatementNode

class TypeParameterNode(TSNode):
    pass

NODE_MAP['type_parameter'] = TypeParameterNode

class TypedDefaultParameterNode(TSNode):
    __match_args__ = ('type_name', 'name', 'type', 'value')
    pass

NODE_MAP['typed_default_parameter'] = TypedDefaultParameterNode

class TypedParameterNode(TSNode):
    __match_args__ = ('type_name', 'type')
    pass

NODE_MAP['typed_parameter'] = TypedParameterNode

class UnaryOperatorNode(TSNode):
    __match_args__ = ('type_name', 'argument', 'operator')
    pass

NODE_MAP['unary_operator'] = UnaryOperatorNode

class UnionPatternNode(TSNode):
    pass

NODE_MAP['union_pattern'] = UnionPatternNode

class UnionTypeNode(TSNode):
    pass

NODE_MAP['union_type'] = UnionTypeNode

class WhileStatementNode(TSNode):
    __match_args__ = ('type_name', 'alternative', 'body', 'condition')
    pass

NODE_MAP['while_statement'] = WhileStatementNode

class WildcardImportNode(TSNode):
    pass

NODE_MAP['wildcard_import'] = WildcardImportNode

class WithClauseNode(TSNode):
    pass

NODE_MAP['with_clause'] = WithClauseNode

class WithItemNode(TSNode):
    __match_args__ = ('type_name', 'value')
    pass

NODE_MAP['with_item'] = WithItemNode

class WithStatementNode(TSNode):
    __match_args__ = ('type_name', 'body')
    pass

NODE_MAP['with_statement'] = WithStatementNode

class YieldExpressionNode(TSNode):
    pass

NODE_MAP['yield'] = YieldExpressionNode

class NotEqualsNode(TSNode):
    pass

NODE_MAP['!='] = NotEqualsNode

class PercentNode(TSNode):
    pass

NODE_MAP['%'] = PercentNode

class ModEqualsNode(TSNode):
    pass

NODE_MAP['%='] = ModEqualsNode

class AmpersandNode(TSNode):
    pass

NODE_MAP['&'] = AmpersandNode

class AmpersandEqualsNode(TSNode):
    pass

NODE_MAP['&='] = AmpersandEqualsNode

class LeftParenNode(TSNode):
    pass

NODE_MAP['('] = LeftParenNode

class RightParenNode(TSNode):
    pass

NODE_MAP[')'] = RightParenNode

class AsteriskNode(TSNode):
    pass

NODE_MAP['*'] = AsteriskNode

class PowerNode(TSNode):
    pass

NODE_MAP['**'] = PowerNode

class PowerEqualsNode(TSNode):
    pass

NODE_MAP['**='] = PowerEqualsNode

class TimesEqualsNode(TSNode):
    pass

NODE_MAP['*='] = TimesEqualsNode

class PlusNode(TSNode):
    pass

NODE_MAP['+'] = PlusNode

class PlusEqualsNode(TSNode):
    pass

NODE_MAP['+='] = PlusEqualsNode

class CommaNode(TSNode):
    pass

NODE_MAP[','] = CommaNode

class MinusNode(TSNode):
    pass

NODE_MAP['-'] = MinusNode

class MinusEqualsNode(TSNode):
    pass

NODE_MAP['-='] = MinusEqualsNode

class ArrowNode(TSNode):
    pass

NODE_MAP['->'] = ArrowNode

class DotNode(TSNode):
    pass

NODE_MAP['.'] = DotNode

class SlashNode(TSNode):
    pass

NODE_MAP['/'] = SlashNode

class FloorDivNode(TSNode):
    pass

NODE_MAP['//'] = FloorDivNode

class FloorDivEqualsNode(TSNode):
    pass

NODE_MAP['//='] = FloorDivEqualsNode

class DivideEqualsNode(TSNode):
    pass

NODE_MAP['/='] = DivideEqualsNode

class ColonNode(TSNode):
    pass

NODE_MAP[':'] = ColonNode

class WalrusNode(TSNode):
    pass

NODE_MAP[':='] = WalrusNode

class SemicolonNode(TSNode):
    pass

NODE_MAP[';'] = SemicolonNode

class LessThanNode(TSNode):
    pass

NODE_MAP['<'] = LessThanNode

class LeftShiftNode(TSNode):
    pass

NODE_MAP['<<'] = LeftShiftNode

class LeftShiftEqualsNode(TSNode):
    pass

NODE_MAP['<<='] = LeftShiftEqualsNode

class LessEqualsNode(TSNode):
    pass

NODE_MAP['<='] = LessEqualsNode

class NotEqualsAltNode(TSNode):
    pass

NODE_MAP['<>'] = NotEqualsAltNode

class EqualsNode(TSNode):
    pass

NODE_MAP['='] = EqualsNode

class EqualityNode(TSNode):
    pass

NODE_MAP['=='] = EqualityNode

class GreaterThanNode(TSNode):
    pass

NODE_MAP['>'] = GreaterThanNode

class GreaterEqualsNode(TSNode):
    pass

NODE_MAP['>='] = GreaterEqualsNode

class RightShiftNode(TSNode):
    pass

NODE_MAP['>>'] = RightShiftNode

class RightShiftEqualsNode(TSNode):
    pass

NODE_MAP['>>='] = RightShiftEqualsNode

class AtNode(TSNode):
    pass

NODE_MAP['@'] = AtNode

class AtEqualsNode(TSNode):
    pass

NODE_MAP['@='] = AtEqualsNode

class LeftBracketNode(TSNode):
    pass

NODE_MAP['['] = LeftBracketNode

class BackslashNode(TSNode):
    pass

NODE_MAP['\\'] = BackslashNode

class RightBracketNode(TSNode):
    pass

NODE_MAP[']'] = RightBracketNode

class CaretNode(TSNode):
    pass

NODE_MAP['^'] = CaretNode

class CaretEqualsNode(TSNode):
    pass

NODE_MAP['^='] = CaretEqualsNode

class UnderscoreNode(TSNode):
    pass

NODE_MAP['_'] = UnderscoreNode

class FutureNode(TSNode):
    pass

NODE_MAP['__future__'] = FutureNode

class LogicalAndNode(TSNode):
    pass

NODE_MAP['and'] = LogicalAndNode

class AsKeywordNode(TSNode):
    pass

NODE_MAP['as'] = AsKeywordNode

class AssertStatementNode(TSNode):
    pass

NODE_MAP['assert'] = AssertStatementNode

class AsyncKeywordNode(TSNode):
    pass

NODE_MAP['async'] = AsyncKeywordNode

class AwaitExpressionNode(TSNode):
    pass

NODE_MAP['await'] = AwaitExpressionNode

class BreakStatementNode(TSNode):
    pass

NODE_MAP['break'] = BreakStatementNode

class CaseClauseNode(TSNode):
    pass

NODE_MAP['case'] = CaseClauseNode

class ClassDefinitionNode(TSNode):
    pass

NODE_MAP['class'] = ClassDefinitionNode

class CommentNode(TSNode):
    pass

NODE_MAP['comment'] = CommentNode

class ContinueStatementNode(TSNode):
    pass

NODE_MAP['continue'] = ContinueStatementNode

class FunctionDefinitionPrefixNode(TSNode):
    pass

NODE_MAP['def'] = FunctionDefinitionPrefixNode

class DeleteStatementNode(TSNode):
    pass

NODE_MAP['del'] = DeleteStatementNode

class ElifStatementNode(TSNode):
    pass

NODE_MAP['elif'] = ElifStatementNode

class EllipsisNode(TSNode):
    pass

NODE_MAP['ellipsis'] = EllipsisNode

class ElseStatementNode(TSNode):
    pass

NODE_MAP['else'] = ElseStatementNode

class EscapeInterpolationNode(TSNode):
    pass

NODE_MAP['escape_interpolation'] = EscapeInterpolationNode

class EscapeSequenceNode(TSNode):
    pass

NODE_MAP['escape_sequence'] = EscapeSequenceNode

class ExceptClauseNode(TSNode):
    pass

NODE_MAP['except'] = ExceptClauseNode

class ExceptStarNode(TSNode):
    pass

NODE_MAP['except*'] = ExceptStarNode

class ExecNode(TSNode):
    pass

NODE_MAP['exec'] = ExecNode

class FalseLiteralNode(TSNode):
    pass

NODE_MAP['false'] = FalseLiteralNode

class FinallyClauseNode(TSNode):
    pass

NODE_MAP['finally'] = FinallyClauseNode

class FloatNode(TSNode):
    pass

NODE_MAP['float'] = FloatNode

class ForStatementNode(TSNode):
    pass

NODE_MAP['for'] = ForStatementNode

class FromStatementNode(TSNode):
    pass

NODE_MAP['from'] = FromStatementNode

class GlobalStatementNode(TSNode):
    pass

NODE_MAP['global'] = GlobalStatementNode

class IdentifierNode(TSNode):
    pass

NODE_MAP['identifier'] = IdentifierNode

class IfStatementNode(TSNode):
    pass

NODE_MAP['if'] = IfStatementNode

class ImportStatementNode(TSNode):
    pass

NODE_MAP['import'] = ImportStatementNode

class InOperatorNode(TSNode):
    pass

NODE_MAP['in'] = InOperatorNode

class IntegerNode(TSNode):
    pass

NODE_MAP['integer'] = IntegerNode

class IsOperatorNode(TSNode):
    pass

NODE_MAP['is'] = IsOperatorNode

class IsNotNode(TSNode):
    pass

NODE_MAP['is not'] = IsNotNode

class LambdaFunctionNode(TSNode):
    pass

NODE_MAP['lambda'] = LambdaFunctionNode

class LineContinuationNode(TSNode):
    pass

NODE_MAP['line_continuation'] = LineContinuationNode

class MatchStatementNode(TSNode):
    pass

NODE_MAP['match'] = MatchStatementNode

class NoneLiteralNode(TSNode):
    pass

NODE_MAP['none'] = NoneLiteralNode

class NonlocalStatementNode(TSNode):
    pass

NODE_MAP['nonlocal'] = NonlocalStatementNode

class LogicalNotNode(TSNode):
    pass

NODE_MAP['not'] = LogicalNotNode

class NotInNode(TSNode):
    pass

NODE_MAP['not in'] = NotInNode

class LogicalOrNode(TSNode):
    pass

NODE_MAP['or'] = LogicalOrNode

class PassStatementNode(TSNode):
    pass

NODE_MAP['pass'] = PassStatementNode

class PrintNode(TSNode):
    pass

NODE_MAP['print'] = PrintNode

class RaiseStatementNode(TSNode):
    pass

NODE_MAP['raise'] = RaiseStatementNode

class ReturnStatementNode(TSNode):
    pass

NODE_MAP['return'] = ReturnStatementNode

class StringEndNode(TSNode):
    pass

NODE_MAP['string_end'] = StringEndNode

class StringStartNode(TSNode):
    pass

NODE_MAP['string_start'] = StringStartNode

class TrueLiteralNode(TSNode):
    pass

NODE_MAP['true'] = TrueLiteralNode

class TryStatementNode(TSNode):
    pass

NODE_MAP['try'] = TryStatementNode

class TypeAliasNode(TSNode):
    pass

NODE_MAP['type'] = TypeAliasNode

class TypeConversionNode(TSNode):
    pass

NODE_MAP['type_conversion'] = TypeConversionNode

class WhileStatementNode(TSNode):
    pass

NODE_MAP['while'] = WhileStatementNode

class WithStatementNode(TSNode):
    pass

NODE_MAP['with'] = WithStatementNode

class YieldExpressionNode(TSNode):
    pass

NODE_MAP['yield'] = YieldExpressionNode

class LeftBraceNode(TSNode):
    pass

NODE_MAP['{'] = LeftBraceNode

class PipeNode(TSNode):
    pass

NODE_MAP['|'] = PipeNode

class PipeEqualsNode(TSNode):
    pass

NODE_MAP['|='] = PipeEqualsNode

class RightBraceNode(TSNode):
    pass

NODE_MAP['}'] = RightBraceNode

class TildeNode(TSNode):
    pass

NODE_MAP['~'] = TildeNode

TSNode.register_subclasses(NODE_MAP)