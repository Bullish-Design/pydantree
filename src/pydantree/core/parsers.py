# pydantree/core/parsers.py
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Type, Union, List
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
import weakref

try:
    from tree_sitter import Language, Parser as _TSParser
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False

from .nodes import TSNode
from .profiler import PerformanceProfiler


class LanguageSupport(Enum):
    """Supported language identifiers."""
    PYTHON = "python"
    JAVASCRIPT = "javascript" 
    TYPESCRIPT = "typescript"
    JSON = "json"
    TOML = "toml"
    YAML = "yaml"
    RUST = "rust"
    GO = "go"
    CPP = "cpp"
    C = "c"
    JAVA = "java"
    CSHARP = "csharp"
    HTML = "html"
    CSS = "css"
    SQL = "sql"
    BASH = "bash"


@dataclass
class LanguageConfig:
    """Configuration for a supported language."""
    name: str
    extensions: List[str]
    tree_sitter_name: str
    package_name: Optional[str] = None
    node_types_path: Optional[Path] = None
    grammar_version: Optional[str] = None
    features: Dict[str, bool] = None
    priority: int = 0  # For language detection ordering
    
    def __post_init__(self):
        if self.features is None:
            self.features = {}


class LanguageRegistry:
    """Registry of supported languages with intelligent detection."""
    
    _languages: Dict[str, LanguageConfig] = {
        "python": LanguageConfig(
            name="python",
            extensions=[".py", ".pyx", ".pyi", ".pyw"],
            tree_sitter_name="python",
            package_name="tree-sitter-python",
            features={"classes": True, "functions": True, "async": True, "decorators": True},
            priority=10
        ),
        "javascript": LanguageConfig(
            name="javascript",
            extensions=[".js", ".mjs", ".cjs", ".jsx"],
            tree_sitter_name="javascript",
            package_name="tree-sitter-javascript",
            features={"classes": True, "functions": True, "async": True, "modules": True},
            priority=9
        ),
        "typescript": LanguageConfig(
            name="typescript",
            extensions=[".ts", ".tsx", ".d.ts"],
            tree_sitter_name="typescript",
            package_name="tree-sitter-typescript",
            features={"classes": True, "functions": True, "async": True, "types": True},
            priority=8
        ),
        "json": LanguageConfig(
            name="json",
            extensions=[".json", ".jsonl", ".json5"],
            tree_sitter_name="json",
            package_name="tree-sitter-json",
            features={"objects": True, "arrays": True},
            priority=7
        ),
        "rust": LanguageConfig(
            name="rust",
            extensions=[".rs"],
            tree_sitter_name="rust",
            package_name="tree-sitter-rust",
            features={"structs": True, "enums": True, "traits": True, "macros": True},
            priority=6
        ),
        "go": LanguageConfig(
            name="go", 
            extensions=[".go"],
            tree_sitter_name="go",
            package_name="tree-sitter-go",
            features={"structs": True, "interfaces": True, "goroutines": True},
            priority=5
        ),
        "java": LanguageConfig(
            name="java",
            extensions=[".java"],
            tree_sitter_name="java", 
            package_name="tree-sitter-java",
            features={"classes": True, "interfaces": True, "annotations": True},
            priority=4
        ),
        "cpp": LanguageConfig(
            name="cpp",
            extensions=[".cpp", ".cxx", ".cc", ".C", ".hpp", ".hxx", ".h"],
            tree_sitter_name="cpp",
            package_name="tree-sitter-cpp",
            features={"classes": True, "templates": True, "namespaces": True},
            priority=3
        ),
        "c": LanguageConfig(
            name="c",
            extensions=[".c", ".h"],
            tree_sitter_name="c",
            package_name="tree-sitter-c",
            features={"structs": True, "unions": True, "macros": True},
            priority=2
        )
    }
    
    @classmethod
    def get_language_config(cls, language: str) -> Optional[LanguageConfig]:
        """Get configuration for language."""
        return cls._languages.get(language.lower())
    
    @classmethod
    def detect_language(cls, file_path: Path) -> Optional[str]:
        """Detect language from file extension with priority ordering."""
        extension = file_path.suffix.lower()
        
        # Handle special cases
        if file_path.name.lower() in {'dockerfile', 'makefile', 'cmakelists.txt'}:
            return None  # Not supported yet
        
        candidates = []
        for lang_name, config in cls._languages.items():
            if extension in config.extensions:
                candidates.append((config.priority, lang_name))
        
        if candidates:
            # Return highest priority match
            candidates.sort(reverse=True)
            return candidates[0][1]
        
        return None
    
    @classmethod
    def detect_from_content(cls, content: str, file_path: Optional[Path] = None) -> Optional[str]:
        """Advanced content-based language detection."""
        content_start = content[:1000].strip()
        
        # Shebang detection
        if content_start.startswith('#!'):
            first_line = content_start.split('\n')[0]
            if 'python' in first_line:
                return "python"
            elif 'node' in first_line or 'javascript' in first_line:
                return "javascript"
            elif 'bash' in first_line or 'sh' in first_line:
                return "bash"
        
        # Content patterns
        patterns = {
            'python': [
                'def ', 'class ', 'import ', 'from ', '__init__',
                'if __name__ == "__main__"', 'self.', '@'
            ],
            'javascript': [
                'function ', 'var ', 'let ', 'const ', '=>', 'require(',
                'module.exports', 'console.log', '&&', '||'
            ],
            'typescript': [
                'interface ', ': string', ': number', ': boolean',
                'type ', 'enum ', 'declare ', 'namespace '
            ],
            'json': [
                content_start.startswith('{') or content_start.startswith('['),
                '":', '",', '"}'
            ],
            'rust': [
                'fn ', 'let ', 'mut ', 'struct ', 'impl ', 'match ',
                'pub ', 'use ', '::',
            ],
            'go': [
                'package ', 'func ', 'import ', 'var ', 'type ',
                'go ', 'chan ', 'defer '
            ],
            'java': [
                'public class', 'private ', 'protected ', 'static ',
                'import java', 'package ', '@Override'
            ],
            'cpp': [
                '#include', 'using namespace', 'std::', '::',
                'template<', 'class ', 'public:', 'private:'
            ]
        }
        
        scores = {}
        for lang, lang_patterns in patterns.items():
            score = 0
            for pattern in lang_patterns:
                if isinstance(pattern, bool):
                    score += 2 if pattern else 0
                elif isinstance(pattern, str) and pattern in content_start:
                    score += 1
            scores[lang] = score
        
        if scores:
            best_lang = max(scores, key=scores.get)
            if scores[best_lang] > 0:
                return best_lang
        
        return None
    
    @classmethod
    def get_supported_languages(cls) -> List[str]:
        """Get list of supported language names sorted by priority."""
        langs = list(cls._languages.items())
        langs.sort(key=lambda x: x[1].priority, reverse=True)
        return [name for name, _ in langs]
    
    @classmethod
    def register_language(cls, config: LanguageConfig) -> None:
        """Register new language configuration."""
        cls._languages[config.name] = config
    
    @classmethod
    def get_extensions(cls) -> Dict[str, str]:
        """Get mapping of extensions to languages."""
        ext_map = {}
        for lang_name, config in cls._languages.items():
            for ext in config.extensions:
                if ext not in ext_map:  # First match wins
                    ext_map[ext] = lang_name
        return ext_map


class ParserPool:
    """Thread-safe parser pool for high-performance concurrent parsing."""
    
    def __init__(self, language: Language, language_name: str, pool_size: int = 10):
        self.language = language
        self.language_name = language_name
        self.pool_size = pool_size
        self._parsers: Queue[_TSParser] = Queue(maxsize=pool_size)
        self._created_count = 0
        self._lock = threading.Lock()
        
        # Pre-populate pool
        for _ in range(min(2, pool_size)):  # Start with 2 parsers
            self._create_parser()
    
    def _create_parser(self) -> _TSParser:
        """Create a new parser instance."""
        parser = _TSParser(self.language)
        with self._lock:
            self._created_count += 1
        return parser
    
    def get_parser(self) -> _TSParser:
        """Get a parser from the pool."""
        try:
            return self._parsers.get_nowait()
        except Empty:
            # Create new parser if pool is empty and we haven't reached limit
            with self._lock:
                if self._created_count < self.pool_size:
                    return self._create_parser()
            
            # Wait for parser to become available
            return self._parsers.get(timeout=5.0)
    
    def return_parser(self, parser: _TSParser) -> None:
        """Return parser to pool."""
        try:
            self._parsers.put_nowait(parser)
        except:
            pass  # Pool is full, let parser be garbage collected


class GrammarLoader:
    """Dynamically load Tree-sitter grammars with caching."""
    
    def __init__(self):
        self._loaded_languages: Dict[str, Language] = {}
        self._parser_pools: Dict[str, ParserPool] = {}
        self._node_registries: Dict[str, Dict[str, Type[TSNode]]] = {}
        self._lock = threading.RLock()
    
    def load_language(self, language_name: str) -> Language:
        """Load Tree-sitter language with caching."""
        if not HAS_TREE_SITTER:
            raise ImportError("tree-sitter is required for parsing")
        
        with self._lock:
            if language_name in self._loaded_languages:
                return self._loaded_languages[language_name]
            
            config = LanguageRegistry.get_language_config(language_name)
            if not config:
                raise ValueError(f"Unsupported language: {language_name}")
            
            language = self._load_tree_sitter_language(config)
            self._loaded_languages[language_name] = language
            
            # Create parser pool
            self._parser_pools[language_name] = ParserPool(language, language_name)
            
            # Generate node classes
            self._generate_node_classes(language_name, config)
            
            return language
    
    def get_parser_pool(self, language_name: str) -> ParserPool:
        """Get parser pool for language."""
        if language_name not in self._parser_pools:
            self.load_language(language_name)
        return self._parser_pools[language_name]
    
    def _load_tree_sitter_language(self, config: LanguageConfig) -> Language:
        """Load Tree-sitter Language object."""
        try:
            # Dynamic import based on language
            if config.name == "python":
                import tree_sitter_python as ts_lang
                return Language(ts_lang.language())
            elif config.name == "javascript":
                import tree_sitter_javascript as ts_lang  
                return Language(ts_lang.language())
            elif config.name == "typescript":
                import tree_sitter_typescript as ts_lang
                return Language(ts_lang.language_typescript())
            elif config.name == "json":
                import tree_sitter_json as ts_lang
                return Language(ts_lang.language())
            elif config.name == "rust":
                import tree_sitter_rust as ts_lang
                return Language(ts_lang.language())
            elif config.name == "go":
                import tree_sitter_go as ts_lang
                return Language(ts_lang.language())
            elif config.name == "java":
                import tree_sitter_java as ts_lang
                return Language(ts_lang.language())
            elif config.name in ["cpp", "c"]:
                import tree_sitter_cpp as ts_lang
                return Language(ts_lang.language())
            else:
                # Generic fallback
                module_name = f"tree_sitter_{config.name.replace('-', '_')}"
                module = __import__(module_name)
                return Language(module.language())
                
        except ImportError as e:
            raise ImportError(
                f"Tree-sitter {config.name} not installed. "
                f"Install with: pip install {config.package_name or f'tree-sitter-{config.name}'}"
            ) from e
    
    def _generate_node_classes(self, language_name: str, config: LanguageConfig) -> None:
        """Generate or load node classes for language."""
        if language_name in self._node_registries:
            return
        
        # For now, use base TSNode for all languages
        # In a full implementation, we'd generate specific classes from node-types.json
        self._node_registries[language_name] = {"__default__": TSNode}
        
        # Register with TSNode
        TSNode.register_subclasses(self._node_registries[language_name])
    
    def get_node_registry(self, language_name: str) -> Dict[str, Type[TSNode]]:
        """Get node registry for language."""
        if language_name not in self._node_registries:
            self.load_language(language_name)
        return self._node_registries.get(language_name, {"__default__": TSNode})


class Parser:
    """High-performance parser with pooling and caching."""
    
    def __init__(self,
                 language: Language,
                 language_name: str,
                 parser_pool: Optional[ParserPool] = None,
                 profiler: Optional[PerformanceProfiler] = None):
        """Initialize parser with language configuration."""
        if not HAS_TREE_SITTER:
            raise ImportError("tree-sitter is required for parsing")
        
        self.language = language
        self.language_name = language_name
        self.parser_pool = parser_pool
        self.profiler = profiler
        self._parse_cache: Dict[str, TSNode] = {}
        self._cache_enabled = True
        self._max_cache_size = 1000
    
    def parse(self, text: str, use_cache: bool = True) -> TSNode:
        """Parse text with optional caching."""
        if self.profiler:
            with self.profiler.profile(f'parse_{self.language_name}'):
                return self._do_parse(text, use_cache)
        else:
            return self._do_parse(text, use_cache)
    
    @lru_cache(maxsize=256)
    def _get_text_hash(self, text: str) -> str:
        """Get hash for text content."""
        import hashlib
        return hashlib.md5(text.encode()).hexdigest()
    
    def _do_parse(self, text: str, use_cache: bool) -> TSNode:
        """Internal parse method with caching."""
        if use_cache and self._cache_enabled:
            text_hash = self._get_text_hash(text)
            if text_hash in self._parse_cache:
                return self._parse_cache[text_hash]
        
        byte_text = text.encode('utf-8')
        
        if self.parser_pool:
            # Use pooled parser
            parser = self.parser_pool.get_parser()
            try:
                tree = parser.parse(byte_text)
                result = TSNode.from_tree_sitter(tree.root_node, byte_text)
            finally:
                self.parser_pool.return_parser(parser)
        else:
            # Create single-use parser
            parser = _TSParser(self.language)
            tree = parser.parse(byte_text)
            result = TSNode.from_tree_sitter(tree.root_node, byte_text)
        
        # Cache result if enabled
        if use_cache and self._cache_enabled:
            if len(self._parse_cache) >= self._max_cache_size:
                # Simple cache eviction - remove oldest half
                items = list(self._parse_cache.items())
                self._parse_cache = dict(items[len(items)//2:])
            
            text_hash = self._get_text_hash(text)
            self._parse_cache[text_hash] = result
        
        return result
    
    def parse_file(self, file_path: Path, encoding: str = 'utf-8') -> TSNode:
        """Parse file with encoding detection."""
        try:
            content = file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            # Try common encodings
            for enc in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    content = file_path.read_text(encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError(f"Could not decode file {file_path}")
        
        return self.parse(content)
    
    def parse_incremental(self, text: str, old_tree) -> TSNode:
        """Incremental parsing for real-time editing."""
        byte_text = text.encode('utf-8')
        
        if self.parser_pool:
            parser = self.parser_pool.get_parser()
            try:
                tree = parser.parse(byte_text, old_tree=old_tree)
                result = TSNode.from_tree_sitter(tree.root_node, byte_text)
            finally:
                self.parser_pool.return_parser(parser)
        else:
            parser = _TSParser(self.language)
            tree = parser.parse(byte_text, old_tree=old_tree)
            result = TSNode.from_tree_sitter(tree.root_node, byte_text)
        
        return result
    
    def clear_cache(self) -> None:
        """Clear parse cache."""
        self._parse_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'cache_size': len(self._parse_cache),
            'max_cache_size': self._max_cache_size,
            'cache_enabled': self._cache_enabled
        }
    
    def get_language_info(self) -> Dict[str, Any]:
        """Get information about loaded language."""
        config = LanguageRegistry.get_language_config(self.language_name)
        return {
            'name': self.language_name,
            'config': config.__dict__ if config else None,
            'cache_stats': self.get_cache_stats(),
            'pool_available': self.parser_pool is not None
        }
    
    # ========================================================================
    # Factory Methods
    # ========================================================================
    
    @classmethod
    def for_language(cls, language_name: str,
                    profiler: Optional[PerformanceProfiler] = None,
                    use_pool: bool = True,
                    **kwargs) -> 'Parser':
        """Create parser for specified language with pooling."""
        loader = GrammarLoader()
        language = loader.load_language(language_name)
        
        parser_pool = loader.get_parser_pool(language_name) if use_pool else None
        
        return cls(
            language=language,
            language_name=language_name,
            parser_pool=parser_pool,
            profiler=profiler,
            **kwargs
        )
    
    @classmethod
    def for_python(cls, profiler: Optional[PerformanceProfiler] = None, **kwargs) -> 'Parser':
        """Create Python parser (backward compatibility)."""
        return cls.for_language("python", profiler=profiler, **kwargs)
    
    @classmethod
    def auto_detect(cls, file_path: Path,
                   profiler: Optional[PerformanceProfiler] = None,
                   **kwargs) -> 'Parser':
        """Create parser by auto-detecting language from file."""
        # Try extension-based detection first
        language_name = LanguageRegistry.detect_language(file_path)
        
        if not language_name:
            # Try content-based detection
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')[:2000]
                language_name = LanguageRegistry.detect_from_content(content, file_path)
            except Exception:
                pass
        
        if not language_name:
            raise ValueError(f"Could not detect language for {file_path}")
        
        return cls.for_language(language_name, profiler=profiler, **kwargs)


class MultiLanguageParser:
    """Parser supporting multiple languages with intelligent selection."""
    
    def __init__(self, language_names: List[str],
                 profiler: Optional[PerformanceProfiler] = None,
                 max_workers: int = 4):
        """Initialize with multiple language support."""
        self.parsers: Dict[str, Parser] = {}
        self.profiler = profiler
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Create parsers for each language
        for lang_name in language_names:
            self.parsers[lang_name] = Parser.for_language(lang_name, profiler=profiler)
        
        # Build extension mapping
        self.extension_map: Dict[str, str] = {}
        for lang_name in language_names:
            config = LanguageRegistry.get_language_config(lang_name)
            if config:
                for ext in config.extensions:
                    if ext not in self.extension_map:  # First match wins
                        self.extension_map[ext] = lang_name
    
    def parse_file(self, file_path: Path) -> TSNode:
        """Parse file using appropriate language parser."""
        language_name = self._detect_language(file_path)
        if not language_name:
            raise ValueError(f"No parser available for {file_path}")
        
        parser = self.parsers[language_name]
        return parser.parse_file(file_path)
    
    def parse_with_language(self, text: str, language_name: str) -> TSNode:
        """Parse text with specified language."""
        if language_name not in self.parsers:
            raise ValueError(f"Language not supported: {language_name}")
        
        return self.parsers[language_name].parse(text)
    
    def parse_batch(self, files: List[Path]) -> Dict[Path, TSNode]:
        """Parse multiple files concurrently."""
        def parse_single(file_path: Path) -> tuple[Path, TSNode]:
            try:
                result = self.parse_file(file_path)
                return file_path, result
            except Exception as e:
                return file_path, None
        
        futures = [self._executor.submit(parse_single, f) for f in files]
        results = {}
        
        for future in futures:
            file_path, result = future.result()
            if result is not None:
                results[file_path] = result
        
        return results
    
    def _detect_language(self, file_path: Path) -> Optional[str]:
        """Detect language for file."""
        # Extension-based detection
        extension = file_path.suffix.lower()
        if extension in self.extension_map:
            return self.extension_map[extension]
        
        # Content-based fallback
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')[:1000]
            return LanguageRegistry.detect_from_content(content, file_path)
        except Exception:
            return None
    
    def get_supported_extensions(self) -> List[str]:
        """Get all supported file extensions."""
        return list(self.extension_map.keys())
    
    def get_parser_for_file(self, file_path: Path) -> Optional[Parser]:
        """Get appropriate parser for file."""
        language_name = self._detect_language(file_path)
        return self.parsers.get(language_name) if language_name else None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all parsers."""
        stats = {}
        for lang_name, parser in self.parsers.items():
            stats[lang_name] = parser.get_cache_stats()
        return stats
    
    def clear_caches(self) -> None:
        """Clear all parser caches."""
        for parser in self.parsers.values():
            parser.clear_cache()
    
    def __del__(self):
        """Cleanup executor."""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)


# Convenience functions with enhanced performance
def parse_python(text: str, profiler: Optional[PerformanceProfiler] = None) -> TSNode:
    """Parse Python text with pooling."""
    parser = Parser.for_python(profiler=profiler)
    return parser.parse(text)


def parse_javascript(text: str, profiler: Optional[PerformanceProfiler] = None) -> TSNode:
    """Parse JavaScript text with pooling."""
    parser = Parser.for_language("javascript", profiler=profiler)
    return parser.parse(text)


def parse_file(file_path: Path, profiler: Optional[PerformanceProfiler] = None) -> TSNode:
    """Parse file with auto-detection and pooling."""
    parser = Parser.auto_detect(file_path, profiler=profiler)
    return parser.parse_file(file_path)


def create_multi_parser(languages: List[str], 
                       profiler: Optional[PerformanceProfiler] = None) -> MultiLanguageParser:
    """Create multi-language parser with specified languages."""
    return MultiLanguageParser(languages, profiler=profiler)


# Global parser instances for common languages (lazy-loaded)
_global_parsers: Dict[str, Parser] = {}
_parser_lock = threading.Lock()


def get_global_parser(language: str) -> Parser:
    """Get cached global parser for language."""
    with _parser_lock:
        if language not in _global_parsers:
            _global_parsers[language] = Parser.for_language(language)
        return _global_parsers[language]
