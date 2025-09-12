# Incremental Parsing - Efficient Text/AST Synchronization

ParsedDocument maintains synchronized text and AST state with efficient incremental re-parsing for interactive editing scenarios.

## Core Concepts

### ParsedDocument - Synchronized State

```python
class ParsedDocument(BaseModel):
    text: str           # Source text
    parser: Parser      # Parser instance
    tree: Tree          # Raw Tree-sitter tree
    root: TSNode        # Validated root node
    
    def edit(self, start_byte: int, old_end_byte: int, 
             new_end_byte: int, new_text: str) -> None
```

### Incremental Algorithm

Tree-sitter only re-parses changed regions:
1. Apply text edit to document
2. Inform Tree-sitter of edit boundaries  
3. Re-parse with existing tree as context
4. Update validated TSNode tree

## Basic Usage

### Document Creation

```python
from pydantree import ParsedDocument, Parser

code = """
def calculate(x, y):
    result = x + y
    return result
"""

parser = Parser.for_python()
doc = ParsedDocument(text=code, parser=parser)

print(f"Initial parse: {len(doc.root.children)} statements")
```

### Simple Edits

```python
# Insert text
doc.edit(
    start_byte=20,
    old_end_byte=20,     # Insert position
    new_end_byte=35,     # After insertion
    new_text=": int, y: int"
)

# Replace text
old_text_start = doc.text.find("result")
old_text_end = old_text_start + len("result")
doc.edit(
    start_byte=old_text_start,
    old_end_byte=old_text_end,
    new_end_byte=old_text_start + len("total"),
    new_text="total"
)

# Delete text
comment_start = doc.text.find("# comment")
comment_end = doc.text.find("\n", comment_start)
doc.edit(
    start_byte=comment_start,
    old_end_byte=comment_end,
    new_end_byte=comment_start,
    new_text=""
)
```

## Advanced Edit Operations

### Position Calculation

Internal helper for byte-to-point conversion:

```python
def _point_for_byte(byte_pos: int, buffer: bytes) -> Tuple[int, int]:
    """Convert byte position to (row, column) point."""
    row = buffer.count(b"\n", 0, byte_pos)
    last_nl = buffer.rfind(b"\n", 0, byte_pos)
    column = byte_pos - (last_nl + 1 if last_nl != -1 else 0)
    return row, column
```

### Multi-Edit Transactions

```python
class DocumentEditor:
    def __init__(self, doc: ParsedDocument):
        self.doc = doc
        self.edits = []
    
    def add_edit(self, start: int, end: int, text: str):
        self.edits.append((start, end, text))
    
    def apply_all(self):
        # Sort edits by position (reverse order for stability)
        self.edits.sort(key=lambda e: e[0], reverse=True)
        
        for start, end, text in self.edits:
            self.doc.edit(start, end, start + len(text), text)
```

### Error Recovery

```python
def safe_edit(doc: ParsedDocument, start: int, end: int, text: str) -> bool:
    """Apply edit with error recovery."""
    original_text = doc.text
    original_tree = doc.tree
    original_root = doc.root
    
    try:
        doc.edit(start, end, start + len(text), text)
        
        # Validate parse succeeded
        if doc.root.find_by_type("ERROR"):
            raise ValueError("Parse error after edit")
            
        return True
        
    except Exception:
        # Restore original state
        doc.text = original_text
        doc.tree = original_tree  
        doc.root = original_root
        return False
```

## Interactive Editor Integration

### Real-time Validation

```python
class LiveCodeAnalyzer:
    def __init__(self, initial_code: str):
        self.doc = ParsedDocument(text=initial_code, parser=Parser.for_python())
        self.error_positions = []
    
    def on_text_change(self, start: int, end: int, new_text: str):
        """Handle editor text changes."""
        self.doc.edit(start, end, start + len(new_text), new_text)
        self.update_diagnostics()
    
    def update_diagnostics(self):
        """Find parse errors and semantic issues."""
        self.error_positions = []
        
        # Find syntax errors
        errors = self.doc.root.find_by_type("ERROR")
        for error in errors:
            self.error_positions.append({
                "type": "syntax_error",
                "start": error.start_point,
                "end": error.end_point,
                "message": f"Syntax error: {error.text}"
            })
        
        # Semantic validation
        from pydantree.views import PyModule
        module = PyModule(self.doc.root, self.doc)
        
        for func in module.functions():
            if not func.has_return() and func.return_type():
                self.error_positions.append({
                    "type": "semantic_warning", 
                    "start": func.start_point,
                    "message": "Function has return type but no return statement"
                })
```

### Completion Support

```python
def get_completions(doc: ParsedDocument, cursor_pos: int) -> List[str]:
    """Provide code completions at cursor position."""
    
    # Find node at cursor
    def find_node_at_position(node: TSNode, pos: int) -> Optional[TSNode]:
        if node.start_byte <= pos <= node.end_byte:
            for child in node.children:
                result = find_node_at_position(child, pos)
                if result:
                    return result
            return node
        return None
    
    current_node = find_node_at_position(doc.root, cursor_pos)
    if not current_node:
        return []
    
    completions = []
    
    # Context-aware completions
    if current_node.type_name == "identifier":
        # Get available names in scope
        module_group = NodeGroup.from_tree(doc.root)
        identifiers = module_group.filter_type("identifier")
        names = {node.text for node in identifiers if node.text.isidentifier()}
        completions.extend(sorted(names))
    
    elif current_node.type_name in ["function_definition", "class_definition"]:
        # Keyword completions
        completions.extend(["def", "class", "if", "for", "while", "try"])
    
    return completions
```

## Performance Optimization

### Edit Batching

```python
class BatchEditor:
    """Efficient batch editing with single re-parse."""
    
    def __init__(self, doc: ParsedDocument):
        self.doc = doc
        self.pending_edits = []
        self.in_batch = False
    
    def __enter__(self):
        self.in_batch = True
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.apply_batch()
        self.in_batch = False
    
    def edit(self, start: int, end: int, text: str):
        if self.in_batch:
            self.pending_edits.append((start, end, text))
        else:
            self.doc.edit(start, end, start + len(text), text)
    
    def apply_batch(self):
        """Apply all edits in optimal order."""
        if not self.pending_edits:
            return
            
        # Merge overlapping edits and apply
        merged = self.merge_edits(self.pending_edits)
        for start, end, text in merged:
            self.doc.edit(start, end, start + len(text), text)
        
        self.pending_edits.clear()

# Usage
with BatchEditor(doc) as editor:
    editor.edit(10, 15, "new_text")
    editor.edit(50, 60, "more_text")
    # Single re-parse when context exits
```

### Change Tracking

```python
class DocumentHistory:
    def __init__(self, doc: ParsedDocument):
        self.doc = doc
        self.snapshots = [(doc.text, doc.root)]
        self.current_index = 0
    
    def save_snapshot(self):
        """Save current state."""
        self.snapshots.append((self.doc.text, self.doc.root))
        self.current_index = len(self.snapshots) - 1
    
    def undo(self) -> bool:
        """Restore previous state."""
        if self.current_index > 0:
            self.current_index -= 1
            text, root = self.snapshots[self.current_index]
            self.doc.text = text
            self.doc.root = root
            # Re-parse to update tree
            byte_text = text.encode()
            self.doc.tree = self.doc.parser._parser.parse(byte_text)
            return True
        return False
```

## Integration Examples

### Language Server Protocol

```python
class LSPDocument:
    def __init__(self, uri: str, initial_text: str):
        self.uri = uri
        self.doc = ParsedDocument(text=initial_text, parser=Parser.for_python())
        self.version = 0
    
    def did_change(self, changes: List[dict]):
        """Handle LSP textDocument/didChange."""
        for change in changes:
            if "range" in change:
                # Incremental change
                range_obj = change["range"]
                start_pos = self.position_to_byte(range_obj["start"])
                end_pos = self.position_to_byte(range_obj["end"])
                
                self.doc.edit(start_pos, end_pos, 
                             start_pos + len(change["text"]), 
                             change["text"])
            else:
                # Full document replacement
                self.doc = ParsedDocument(text=change["text"], 
                                        parser=self.doc.parser)
        
        self.version += 1
    
    def position_to_byte(self, position: dict) -> int:
        """Convert LSP position to byte offset."""
        lines = self.doc.text.split('\n')
        byte_offset = sum(len(line) + 1 for line in lines[:position["line"]])
        return byte_offset + position["character"]
```

### Code Formatting Integration

```python
def format_on_save(doc: ParsedDocument) -> str:
    """Format code maintaining parse tree."""
    from pydantree.views import PyTransformer
    
    class FormattingTransformer(PyTransformer):
        def visit_function_definition(self, node):
            # Normalize function formatting
            lines = node.text.split('\n')
            formatted_lines = []
            
            for line in lines:
                stripped = line.strip()
                if stripped:
                    # Apply consistent indentation
                    indent = "    " * self.get_indent_level(node)
                    formatted_lines.append(indent + stripped)
                else:
                    formatted_lines.append("")
            
            return '\n'.join(formatted_lines)
    
    module = PyModule(doc.root, doc)
    return FormattingTransformer(module).visit()
```

ParsedDocument enables responsive editing experiences with minimal computational overhead through Tree-sitter's incremental parsing capabilities.