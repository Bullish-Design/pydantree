# skills/treesitter-grammar-dev/SKILL.md
# Tree-sitter Grammar Development Skill

## Overview

This skill provides patterns and practices for working with tree-sitter grammars: writing grammar.js files, compiling parsers, running tests, and debugging parse trees.

## Grammar Lifecycle

### 1. Grammar Definition (grammar.js)

Tree-sitter grammars are written in JavaScript DSL:

```javascript
module.exports = grammar({
  name: 'my_language',
  
  rules: {
    source_file: $ => repeat($._statement),
    
    _statement: $ => choice(
      $.function_declaration,
      $.variable_declaration,
      $.expression_statement
    ),
    
    function_declaration: $ => seq(
      'def',
      field('name', $.identifier),
      field('parameters', $.parameter_list),
      ':',
      field('body', $.block)
    ),
    
    identifier: $ => /[a-zA-Z_][a-zA-Z0-9_]*/,
    
    block: $ => seq(
      'indent',
      repeat1($._statement),
      'dedent'
    )
  }
});
```

**Key concepts:**
- `$` refers to the grammar rules object
- `seq()` = sequence of items in order
- `choice()` = one of several alternatives
- `repeat()` = zero or more
- `repeat1()` = one or more
- `optional()` = zero or one
- `field()` = named field in AST
- `_prefixed` rules = hidden nodes (not in AST)

### 2. Parser Generation

```bash
tree-sitter generate
```

**What this does:**
- Reads `grammar.js`
- Generates `src/parser.c` (the LR parser tables)
- May generate `src/tree_sitter/<name>.h`
- Creates `.node-types.json` (AST node schema)

**Common errors:**
- Left recursion: Grammar has indirect left recursion (not allowed)
- Ambiguity: Multiple parse trees possible (resolve with `prec()`)
- Conflicts: Shift/reduce or reduce/reduce conflicts

### 3. Custom Scanner (Optional)

For context-sensitive lexing (indentation, heredocs, string interpolation):

**C scanner (`src/scanner.c`):**
```c
#include <tree_sitter/parser.h>

enum TokenType {
  INDENT,
  DEDENT,
  NEWLINE
};

void *tree_sitter_my_language_external_scanner_create() {
  return NULL;
}

void tree_sitter_my_language_external_scanner_destroy(void *payload) {}

unsigned tree_sitter_my_language_external_scanner_serialize(
  void *payload,
  char *buffer
) {
  return 0;
}

void tree_sitter_my_language_external_scanner_deserialize(
  void *payload,
  const char *buffer,
  unsigned length
) {}

bool tree_sitter_my_language_external_scanner_scan(
  void *payload,
  TSLexer *lexer,
  const bool *valid_symbols
) {
  // Custom lexing logic here
  if (valid_symbols[INDENT]) {
    // Check if we should emit INDENT token
  }
  return false;
}
```

**C++ scanner (`src/scanner.cc`):**
Same API but can use C++ features (vectors, strings, etc.)

### 4. Compilation

**Linux:**
```bash
gcc -shared -fPIC -O2 -I./src src/parser.c -o parser.so
# With scanner:
gcc -shared -fPIC -O2 -I./src src/parser.c src/scanner.c -o parser.so
```

**macOS:**
```bash
gcc -dynamiclib -fPIC -O2 -I./src src/parser.c -o parser.so
```

**With C++ scanner:**
```bash
g++ -shared -fPIC -O2 -I./src src/parser.c src/scanner.cc -o parser.so
```

### 5. Testing

**Corpus tests (`test/corpus/*.txt`):**
```
==================
Function declaration
==================

def greet(name):
  print(name)

---

(source_file
  (function_declaration
    name: (identifier)
    parameters: (parameter_list
      (identifier))
    body: (block
      (expression_statement
        (call
          function: (identifier)
          arguments: (argument_list
            (identifier)))))))
```

**Format:**
- `==================` separates test cases
- Test name on line after first separator
- Source code to parse
- `---` separator
- Expected AST in S-expression format

**Run tests:**
```bash
tree-sitter test
# Or specific test:
tree-sitter test -f "function declaration"
```

### 6. Interactive Parsing

```bash
# Parse file and show tree
tree-sitter parse example.txt

# Parse to JSON
tree-sitter parse example.txt --json

# Use custom grammar
tree-sitter parse example.txt --language ./parser.so
```

### 7. Highlighting (Optional)

Query files for syntax highlighting in `queries/highlights.scm`:

```scheme
; Highlighting queries
(function_declaration
  name: (identifier) @function)

(call
  function: (identifier) @function.call)

(string) @string
(number) @number
(comment) @comment

["def" "class" "return"] @keyword
```

## Common Patterns

### Precedence and Associativity

**Left associative operators:**
```javascript
expression: $ => choice(
  $.binary_expression,
  $.primary_expression
),

binary_expression: $ => prec.left(choice(
  prec.left(10, seq($.expression, '+', $.expression)),
  prec.left(10, seq($.expression, '-', $.expression)),
  prec.left(20, seq($.expression, '*', $.expression)),
  prec.left(20, seq($.expression, '/', $.expression))
))
```

**Right associative:**
```javascript
assignment: $ => prec.right(seq(
  $.identifier,
  '=',
  $.expression
))
```

### Field Names for AST Navigation

```javascript
function_call: $ => seq(
  field('function', $.identifier),
  '(',
  field('arguments', optional($.argument_list)),
  ')'
)
```

**Benefits:**
- Semantic clarity in AST
- Easier tree-sitter query writing
- Better error messages

### External Tokens for Context

When lexing depends on parser state:

```javascript
module.exports = grammar({
  name: 'my_language',
  
  externals: $ => [
    $.indent,
    $.dedent,
    $.newline
  ],
  
  // ... rest of grammar
});
```

External scanner handles these tokens.

### Hiding Intermediate Nodes

Prefix with `_` to hide from final AST:

```javascript
_statement: $ => choice(
  $.return_statement,
  $.expression_statement,
  $.declaration
)
```

Result: AST has `return_statement`, not `_statement` nodes.

## Debugging Strategies

### Parse Tree Inspection

```bash
# View full parse tree
tree-sitter parse file.txt

# Look for ERROR nodes
tree-sitter parse file.txt | grep ERROR
```

**Common issues:**
- ERROR nodes indicate failed parse
- Check surrounding context for grammar gaps

### Conflict Resolution

```bash
tree-sitter generate --log
```

**Read conflict messages:**
- Shift/reduce: Parser unsure whether to shift token or reduce rule
- Reduce/reduce: Multiple rules could apply

**Solutions:**
- Add `prec()` to disambiguate
- Rewrite grammar to avoid ambiguity
- Use external scanner for context

### Test-Driven Development

1. Write failing test in `test/corpus/`
2. Run `tree-sitter test` to see mismatch
3. Adjust grammar
4. Run `tree-sitter generate`
5. Repeat until test passes

### Binary Search for Regressions

If tests suddenly fail:
1. Binary search through recent commits
2. Compare `.node-types.json` between versions
3. Check for breaking changes in tree-sitter CLI version

## Performance Considerations

### Parse Speed

- Avoid exponential blowup in `repeat(choice(...))` patterns
- Use external scanner for complex lexing (faster than parser)
- Profile with `tree-sitter parse --time file.txt`

### Memory Usage

- Large grammars produce large parser tables (src/parser.c size)
- Consider splitting very complex grammars
- Test with realistic file sizes, not just toy examples

## Integration with Grammatic

**Expected workflow:**
1. Grammar lives in `grammars/<name>/` as git submodule
2. Run `just generate <name>` to create parser.c
3. Run `just build <name>` to compile .so
4. Run `just test-grammar <name>` for corpus tests
5. Run `just parse <name> file.txt` for ad-hoc testing

**Build script handles:**
- Scanner detection (C vs C++)
- Compiler selection (gcc vs g++)
- Platform-specific flags
- Output to `build/<name>.so`

**Log writer captures:**
- Grammar commit hash (version tracking)
- Build success/failure
- Build time
- Parse node count
- Parse errors

## References

- Tree-sitter docs: https://tree-sitter.github.io/tree-sitter/
- Creating parsers guide: https://tree-sitter.github.io/tree-sitter/creating-parsers
- Example grammars: https://github.com/tree-sitter
- Query syntax: https://tree-sitter.github.io/tree-sitter/using-parsers#pattern-matching-with-queries
