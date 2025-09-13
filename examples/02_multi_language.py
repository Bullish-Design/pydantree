# examples/02_multi_language.py

"""Multi-language support and auto-detection examples."""

from pathlib import Path
from pydantree import Parser, get_language, detect_language, get_supported_languages
from pydantree.core.parsers import MultiLanguageParser
from pydantree.languages.registry import get_global_registry

# Example 1: Auto-detect language from file
def auto_detect_language():
    """Demonstrate automatic language detection."""
    
    # Test files with different extensions
    test_files = [
        ("script.py", "Python"),
        ("app.js", "JavaScript"),
        ("component.tsx", "TypeScript"),
        ("main.rs", "Rust"),
        ("config.json", "JSON")
    ]
    
    registry = get_global_registry()
    
    print("Language Detection Results:")
    for filename, expected in test_files:
        file_path = Path(filename)
        detected = registry.detect_language(file_path)
        print(f"  {filename:15} -> {detected or 'Unknown':10} (expected: {expected})")
    
    return registry

# Example 2: Multi-language parser
def multi_language_parsing():
    """Parse different languages with a single parser."""
    
    # Create multi-language parser
    supported_langs = get_supported_languages()
    parser = MultiLanguageParser(supported_langs)
    
    print(f"Supported languages: {supported_langs}")
    print(f"Supported extensions: {parser.get_supported_extensions()}")
    
    # Python code
    python_code = '''
def greet(name):
    return f"Hello, {name}!"

class Person:
    def __init__(self, name):
        self.name = name
'''
    
    # JavaScript code
    js_code = '''
function greet(name) {
    return `Hello, ${name}!`;
}

class Person {
    constructor(name) {
        this.name = name;
    }
}
'''
    
    # Parse with explicit language
    py_ast = parser.parse_with_language(python_code, "python")
    js_ast = parser.parse_with_language(js_code, "javascript")
    
    print(f"\nPython AST root: {py_ast.type_name}")
    print(f"JavaScript AST root: {js_ast.type_name}")
    
    # Find functions in both
    py_functions = py_ast.find_all_by_type("function_definition")
    js_functions = js_ast.find_all_by_type("function_definition")
    
    print(f"Python functions: {len(py_functions)}")
    print(f"JavaScript functions: {len(js_functions)}")
    
    return parser, py_ast, js_ast

# Example 3: Content-based detection
def content_based_detection():
    """Detect language from code content."""
    
    code_samples = [
        ("def main():\n    print('Hello')", "Python"),
        ("function main() {\n    console.log('Hello');\n}", "JavaScript"),
        ("fn main() {\n    println!(\"Hello\");\n}", "Rust"),
        ("{\n  \"name\": \"test\",\n  \"version\": \"1.0\"\n}", "JSON")
    ]
    
    parser = MultiLanguageParser(get_supported_languages())
    
    print("Content-based Language Detection:")
    for code, expected in code_samples:
        detected = parser.detect_language_from_content(code)
        print(f"  Expected: {expected:10} Detected: {detected or 'Unknown'}")
        
        # Try parsing with detected language
        if detected:
            try:
                ast = parser.parse_with_language(code, detected)
                print(f"    Parsed successfully as {detected}")
            except Exception as e:
                print(f"    Parse failed: {e}")
        print()

# Example 4: Language-specific features
def language_specific_features():
    """Explore language-specific AST features."""
    
    # Python with decorators and async
    python_code = '''
import asyncio
from typing import List

@property
def cached_value(self):
    return self._cache

@staticmethod
async def fetch_data(url: str) -> List[dict]:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

class APIClient:
    def __init__(self):
        self._cache = {}
    
    @cached_value
    def get_cache(self):
        pass
'''
    
    # TypeScript with interfaces and generics
    typescript_code = '''
interface User {
    id: number;
    name: string;
    email?: string;
}

type ApiResponse<T> = {
    data: T;
    status: number;
    message?: string;
};

class UserService {
    async fetchUser(id: number): Promise<ApiResponse<User>> {
        const response = await fetch(`/api/users/${id}`);
        return response.json();
    }
}

export { User, UserService };
'''
    
    # Parse both
    python_parser = Parser.for_language("python")
    py_ast = python_parser.parse(python_code)
    
    # Find Python-specific constructs
    decorators = py_ast.find_all_by_type("decorator")
    async_defs = py_ast.find_all_by_type("async")
    imports = py_ast.find_all_by_type({"import_statement", "import_from_statement"})
    
    print("Python Language Features:")
    print(f"  Decorators: {len(decorators)}")
    print(f"  Async constructs: {len(async_defs)}")
    print(f"  Import statements: {len(imports)}")
    
    # List decorator names
    for decorator in decorators:
        name_node = decorator.child_by_field_name("name")
        if name_node:
            print(f"    @{name_node.text}")
    
    # If TypeScript is available
    try:
        ts_parser = Parser.for_language("typescript")
        ts_ast = ts_parser.parse(typescript_code)
        
        interfaces = ts_ast.find_all_by_type("interface_declaration")
        type_aliases = ts_ast.find_all_by_type("type_alias_declaration")
        
        print(f"\nTypeScript Language Features:")
        print(f"  Interfaces: {len(interfaces)}")
        print(f"  Type aliases: {len(type_aliases)}")
        
    except Exception as e:
        print(f"\nTypeScript not available: {e}")

# Example 5: Comparing syntax across languages
def compare_languages():
    """Compare similar constructs across different languages."""
    
    function_examples = {
        "python": "def greet(name):\n    return f'Hello {name}'",
        "javascript": "function greet(name) {\n    return `Hello ${name}`;\n}",
        "rust": "fn greet(name: &str) -> String {\n    format!(\"Hello {}\", name)\n}"
    }
    
    print("Function Definition Comparison:")
    
    for lang, code in function_examples.items():
        try:
            parser = Parser.for_language(lang)
            ast = parser.parse(code)
            
            # Find function definitions
            if lang == "python":
                functions = ast.find_all_by_type("function_definition")
            elif lang == "javascript":
                functions = ast.find_all_by_type("function_definition")
            elif lang == "rust":
                functions = ast.find_all_by_type("function_item")
            else:
                functions = ast.find_all_by_type("function")
            
            print(f"\n{lang.title()}:")
            print(f"  Code: {code.replace(chr(10), ' | ')}")
            print(f"  Root type: {ast.type_name}")
            print(f"  Functions found: {len(functions)}")
            
            if functions:
                func = functions[0]
                print(f"  Function node type: {func.type_name}")
                
                # Try to get function name
                name_node = func.child_by_field_name("name")
                if name_node:
                    print(f"  Function name: {name_node.text}")
                
        except Exception as e:
            print(f"\n{lang.title()}: Not available ({e})")

if __name__ == "__main__":
    print("=== Multi-Language Support Examples ===\n")
    
    print("1. Auto-detect language:")
    auto_detect_language()
    
    print("\n2. Multi-language parsing:")
    multi_language_parsing()
    
    print("\n3. Content-based detection:")
    content_based_detection()
    
    print("\n4. Language-specific features:")
    language_specific_features()
    
    print("\n5. Compare languages:")
    compare_languages()
