# pydantree/core/universal.py
from __future__ import annotations

import re
import importlib
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Protocol
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from .errors import LanguageNotSupportedError, handle_import_error
from ..languages.registry import LanguageConfig, LanguageFeature, LanguagePriority


class GrammarDiscoverer:
    """Auto-discovers available tree-sitter grammars."""
    
    KNOWN_GRAMMARS = {
        "python": {
            "package": "tree-sitter-python", 
            "extensions": [".py", ".pyi"],
            "patterns": ["def ", "class ", "import "],
            "priority": LanguagePriority.HIGH
        },
        "javascript": {
            "package": "tree-sitter-javascript",
            "extensions": [".js", ".mjs"],
            "patterns": ["function ", "const ", "let "],
            "priority": LanguagePriority.HIGH
        },
        "typescript": {
            "package": "tree-sitter-typescript",
            "extensions": [".ts", ".tsx"],
            "patterns": ["interface ", "type ", ": "],
            "priority": LanguagePriority.HIGH
        },
        "rust": {
            "package": "tree-sitter-rust",
            "extensions": [".rs"],
            "patterns": ["fn ", "struct ", "impl "],
            "priority": LanguagePriority.NORMAL
        },
        "go": {
            "package": "tree-sitter-go",
            "extensions": [".go"],
            "patterns": ["func ", "package ", "type "],
            "priority": LanguagePriority.NORMAL
        },
        "java": {
            "package": "tree-sitter-java",
            "extensions": [".java"],
            "patterns": ["public class ", "interface ", "package "],
            "priority": LanguagePriority.NORMAL
        },
        "cpp": {
            "package": "tree-sitter-cpp",
            "extensions": [".cpp", ".cc", ".cxx", ".hpp", ".h"],
            "patterns": ["#include", "class ", "namespace "],
            "priority": LanguagePriority.NORMAL
        },
        "c": {
            "package": "tree-sitter-c",
            "extensions": [".c", ".h"],
            "patterns": ["#include", "struct ", "typedef "],
            "priority": LanguagePriority.NORMAL
        },
        "json": {
            "package": "tree-sitter-json",
            "extensions": [".json"],
            "patterns": ["{", "["],
            "priority": LanguagePriority.LOW
        },
        "yaml": {
            "package": "tree-sitter-yaml",
            "extensions": [".yml", ".yaml"],
            "patterns": ["---", ": "],
            "priority": LanguagePriority.LOW
        }
    }
    
    def discover_available_grammars(self) -> List[LanguageConfig]:
        """Discover all available tree-sitter grammars."""
        available = []
        
        for name, info in self.KNOWN_GRAMMARS.items():
            if self._is_grammar_available(info["package"]):
                config = LanguageConfig(
                    name=name,
                    display_name=name.title(),
                    extensions=info["extensions"],
                    tree_sitter_name=name,
                    package_name=info["package"],
                    features=self._infer_features(name),
                    priority=info["priority"],
                    content_patterns=info["patterns"]
                )
                available.append(config)
        
        return available
    
    def _is_grammar_available(self, package_name: str) -> bool:
        """Check if a tree-sitter grammar package is available."""
        try:
            module_name = package_name.replace("-", "_")
            importlib.import_module(module_name)
            return True
        except ImportError:
            return False
    
    def _infer_features(self, language: str) -> Set[LanguageFeature]:
        """Infer language features based on language type."""
        features = set()
        
        if language in ["python", "javascript", "typescript", "java", "cpp", "rust", "go"]:
            features.update([
                LanguageFeature.CLASSES,
                LanguageFeature.FUNCTIONS,
                LanguageFeature.MODULES
            ])
        
        if language in ["python", "javascript", "typescript", "rust"]:
            features.add(LanguageFeature.ASYNC)
        
        if language in ["python", "java", "typescript"]:
            features.add(LanguageFeature.DECORATORS)
        
        return features


class ContentBasedDetector:
    """Detects programming language from file content."""
    
    def __init__(self):
        self.detectors = [
            self._detect_shebang,
            self._detect_by_patterns,
            self._detect_by_structure,
            self._detect_by_keywords
        ]
    
    def detect_language(self, content: str, file_path: Optional[Path] = None) -> Optional[str]:
        """Detect language from content with confidence scoring."""
        scores: Dict[str, float] = {}
        
        for detector in self.detectors:
            results = detector(content, file_path)
            for lang, score in results.items():
                scores[lang] = scores.get(lang, 0) + score
        
        if not scores:
            return None
        
        # Return language with highest confidence
        best_lang = max(scores.items(), key=lambda x: x[1])
        return best_lang[0] if best_lang[1] > 0.3 else None  # Minimum confidence threshold
    
    def _detect_shebang(self, content: str, file_path: Optional[Path] = None) -> Dict[str, float]:
        """Detect from shebang line."""
        lines = content.split('\n', 1)
        if not lines or not lines[0].startswith('#!'):
            return {}
        
        shebang = lines[0].lower()
        
        if 'python' in shebang:
            return {"python": 0.9}
        elif 'node' in shebang or 'js' in shebang:
            return {"javascript": 0.9}
        elif 'bash' in shebang or 'sh' in shebang:
            return {"bash": 0.9}
        
        return {}
    
    def _detect_by_patterns(self, content: str, file_path: Optional[Path] = None) -> Dict[str, float]:
        """Detect by language-specific patterns."""
        scores = {}
        
        # Python patterns
        python_patterns = [
            r'\bdef\s+\w+\s*\(',  # function definitions
            r'\bclass\s+\w+\s*[\(:]',  # class definitions
            r'\bimport\s+\w+',  # imports
            r'\bfrom\s+\w+\s+import',  # from imports
            r'if\s+__name__\s*==\s*[\'"]__main__[\'"]'  # main guard
        ]
        scores["python"] = self._count_pattern_matches(content, python_patterns) * 0.2
        
        # JavaScript patterns
        js_patterns = [
            r'\bfunction\s+\w+\s*\(',  # function declarations
            r'\bconst\s+\w+\s*=',  # const declarations
            r'\blet\s+\w+\s*=',  # let declarations
            r'\bvar\s+\w+\s*=',  # var declarations
            r'=>',  # arrow functions
            r'\.addEventListener\(',  # DOM events
        ]
        scores["javascript"] = self._count_pattern_matches(content, js_patterns) * 0.2
        
        # TypeScript patterns
        ts_patterns = [
            r'\binterface\s+\w+',  # interface declarations
            r'\btype\s+\w+\s*=',  # type aliases
            r':\s*\w+(\[\])?(\s*\|\s*\w+)*\s*[;,=]',  # type annotations
            r'\bas\s+\w+',  # type assertions
        ]
        scores["typescript"] = self._count_pattern_matches(content, ts_patterns) * 0.2
        
        return scores
    
    def _detect_by_structure(self, content: str, file_path: Optional[Path] = None) -> Dict[str, float]:
        """Detect by structural elements."""
        scores = {}
        
        # JSON structure
        content_stripped = content.strip()
        if (content_stripped.startswith('{') and content_stripped.endswith('}')) or \
           (content_stripped.startswith('[') and content_stripped.endswith(']')):
            try:
                import json
                json.loads(content)
                scores["json"] = 0.8
            except json.JSONDecodeError:
                pass
        
        # YAML structure
        if re.search(r'^---\s*$', content, re.MULTILINE) or \
           re.search(r'^\w+:\s*\w+', content, re.MULTILINE):
            scores["yaml"] = 0.3
        
        return scores
    
    def _detect_by_keywords(self, content: str, file_path: Optional[Path] = None) -> Dict[str, float]:
        """Detect by programming language keywords."""
        content_words = set(re.findall(r'\b\w+\b', content.lower()))
        
        # Language-specific keywords
        python_keywords = {"def", "class", "import", "from", "elif", "lambda", "yield", "async", "await"}
        rust_keywords = {"fn", "struct", "impl", "trait", "match", "mut", "pub", "use"}
        go_keywords = {"func", "package", "import", "interface", "struct", "chan", "select"}
        java_keywords = {"public", "private", "protected", "interface", "extends", "implements", "synchronized"}
        
        scores = {}
        scores["python"] = len(content_words & python_keywords) * 0.1
        scores["rust"] = len(content_words & rust_keywords) * 0.1
        scores["go"] = len(content_words & go_keywords) * 0.1
        scores["java"] = len(content_words & java_keywords) * 0.1
        
        return scores
    
    def _count_pattern_matches(self, content: str, patterns: List[str]) -> int:
        """Count matches for a list of regex patterns."""
        total = 0
        for pattern in patterns:
            total += len(re.findall(pattern, content, re.MULTILINE | re.IGNORECASE))
        return total


class UniversalNodeMapper:
    """Maps language-specific node types to universal semantic types."""
    
    UNIVERSAL_MAPPINGS = {
        # Function-like constructs
        "function": ["function_definition", "function_declaration", "method_definition", "arrow_function"],
        "method": ["method_definition", "function_definition"],  # Context-dependent
        "lambda": ["lambda", "arrow_function", "closure_expression"],
        
        # Class-like constructs
        "class": ["class_definition", "class_declaration", "struct_item", "interface_declaration"],
        "interface": ["interface_declaration", "trait_item"],
        "enum": ["enum_declaration", "enum_item"],
        
        # Variable-like constructs
        "variable": ["variable_declaration", "assignment", "identifier"],
        "parameter": ["parameter", "formal_parameter"],
        "field": ["field_declaration", "field_definition"],
        
        # Control flow
        "conditional": ["if_statement", "elif_clause", "else_clause", "conditional_expression"],
        "loop": ["for_statement", "while_statement", "loop_statement"],
        "match": ["match_statement", "switch_statement", "case_statement"],
        
        # Module system
        "import": ["import_statement", "import_from_statement", "use_declaration"],
        "export": ["export_statement", "pub_item"],
        "module": ["module", "package_declaration", "mod_item"],
        
        # Literals
        "string": ["string", "string_literal", "raw_string_literal"],
        "number": ["integer", "float", "number", "numeric_literal"],
        "boolean": ["true", "false", "boolean_literal"],
        
        # Comments and documentation
        "comment": ["comment", "line_comment", "block_comment"],
        "docstring": ["string", "doc_comment"],  # Context-dependent
    }
    
    def map_to_universal(self, node_type: str, language: str) -> Optional[str]:
        """Map a language-specific node type to universal type."""
        for universal_type, specific_types in self.UNIVERSAL_MAPPINGS.items():
            if node_type in specific_types:
                return universal_type
        return None
    
    def get_semantic_category(self, universal_type: str) -> str:
        """Get high-level semantic category."""
        categories = {
            "declaration": ["function", "method", "class", "interface", "enum", "variable", "field"],
            "control_flow": ["conditional", "loop", "match"],
            "module_system": ["import", "export", "module"],
            "literal": ["string", "number", "boolean"],
            "documentation": ["comment", "docstring"]
        }
        
        for category, types in categories.items():
            if universal_type in types:
                return category
        
        return "other"


class UniversalGrammarSystem:
    """Unified system for multi-language grammar management."""
    
    def __init__(self):
        self.discoverer = GrammarDiscoverer()
        self.detector = ContentBasedDetector()
        self.mapper = UniversalNodeMapper()
        self._available_languages: Dict[str, LanguageConfig] = {}
        self._refresh_available_languages()
    
    def _refresh_available_languages(self):
        """Refresh the list of available languages."""
        configs = self.discoverer.discover_available_grammars()
        self._available_languages = {config.name: config for config in configs}
    
    def get_available_languages(self) -> List[str]:
        """Get list of available language names."""
        return list(self._available_languages.keys())
    
    def get_language_config(self, language: str) -> Optional[LanguageConfig]:
        """Get configuration for a specific language."""
        return self._available_languages.get(language)
    
    def detect_language_comprehensive(self, content: str, file_path: Optional[Path] = None) -> Optional[str]:
        """Comprehensive language detection using multiple methods."""
        # 1. File extension based detection
        if file_path:
            ext = file_path.suffix.lower()
            for config in self._available_languages.values():
                if ext in config.extensions:
                    return config.name
        
        # 2. Content-based detection
        detected = self.detector.detect_language(content, file_path)
        if detected and detected in self._available_languages:
            return detected
        
        return None
    
    def get_universal_mapping(self, node_type: str, language: str) -> Optional[str]:
        """Get universal mapping for a node type."""
        return self.mapper.map_to_universal(node_type, language)
    
    def analyze_language_support(self) -> Dict[str, Any]:
        """Analyze current language support status."""
        all_known = set(self.discoverer.KNOWN_GRAMMARS.keys())
        available = set(self._available_languages.keys())
        missing = all_known - available
        
        return {
            "total_known": len(all_known),
            "available": len(available),
            "missing": len(missing),
            "coverage_percent": (len(available) / len(all_known)) * 100,
            "available_languages": list(available),
            "missing_languages": list(missing),
            "installation_commands": [
                f"pip install {self.discoverer.KNOWN_GRAMMARS[lang]['package']}"
                for lang in missing
            ]
        }
    
    def suggest_language_installs(self) -> List[str]:
        """Suggest language packages to install for better coverage."""
        missing = set(self.discoverer.KNOWN_GRAMMARS.keys()) - set(self._available_languages.keys())
        
        # Prioritize high-priority languages
        high_priority = [
            lang for lang in missing 
            if self.discoverer.KNOWN_GRAMMARS[lang]["priority"] == LanguagePriority.HIGH
        ]
        
        return [
            f"pip install {self.discoverer.KNOWN_GRAMMARS[lang]['package']}"
            for lang in (high_priority + list(missing - set(high_priority)))[:5]
        ]
