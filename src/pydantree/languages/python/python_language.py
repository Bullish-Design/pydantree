# pydantree/languages/python/python_language.py
from ..base import Language, LanguageAnalyzer
from ...core.parsers import Parser
from .python_analyzer import PythonAnalyzer


class PythonLanguage(Language):
    """The concrete implementation for the Python language."""

    def _initialize_components(self):
        """Initializes Python-specific parser and semantic analyzer."""
        self._parser = Parser.for_language("python")
        self._analyzer = PythonAnalyzer(self.config)
