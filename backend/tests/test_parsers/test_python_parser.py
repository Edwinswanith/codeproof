"""Tests for Python parser using tree-sitter.

These tests verify that the parser correctly extracts:
- Functions (with signatures, docstrings, bodies)
- Classes (with methods)
- Imports (regular and from imports)
- Nested structures
"""

import pytest
from app.parsers.python_parser import PythonParser, Symbol, Import


class TestPythonParserFunctions:
    """Test function extraction."""

    def test_parse_simple_function(self, sample_python_simple):
        """Parser extracts a simple function with docstring."""
        parser = PythonParser()
        result = parser.parse(sample_python_simple, "test.py")

        assert len(result.symbols) == 1
        func = result.symbols[0]

        assert func.name == "hello_world"
        assert func.type == "function"
        assert func.file_path == "test.py"
        assert func.line_start == 2
        assert func.docstring == "A simple greeting function."
        assert "return" in func.body

    def test_parse_function_signature(self, sample_python_imports):
        """Parser extracts function with type hints."""
        parser = PythonParser()
        result = parser.parse(sample_python_imports, "test.py")

        # Find the process_data function
        funcs = [s for s in result.symbols if s.type == "function"]
        assert len(funcs) == 1

        func = funcs[0]
        assert func.name == "process_data"
        assert "items: List[str]" in func.signature
        assert "Optional[dict]" in func.signature

    def test_parse_async_function(self, sample_python_complex):
        """Parser handles async functions."""
        parser = PythonParser()
        result = parser.parse(sample_python_complex, "test.py")

        async_funcs = [s for s in result.symbols if s.name == "async_process"]
        assert len(async_funcs) == 1
        assert async_funcs[0].type == "function"


class TestPythonParserClasses:
    """Test class extraction."""

    def test_parse_class_basic(self, sample_python_class):
        """Parser extracts class with methods."""
        parser = PythonParser()
        result = parser.parse(sample_python_class, "test.py")

        classes = [s for s in result.symbols if s.type == "class"]
        assert len(classes) == 1

        calc = classes[0]
        assert calc.name == "Calculator"
        assert calc.docstring == "A simple calculator class."

    def test_parse_class_methods(self, sample_python_class):
        """Parser extracts class methods as children."""
        parser = PythonParser()
        result = parser.parse(sample_python_class, "test.py")

        calc = [s for s in result.symbols if s.type == "class"][0]

        # Methods should be children of the class
        method_names = {c.name for c in calc.children}
        assert "__init__" in method_names
        assert "add" in method_names
        assert "subtract" in method_names

    def test_parse_method_has_parent(self, sample_python_class):
        """Methods should reference their parent class."""
        parser = PythonParser()
        result = parser.parse(sample_python_class, "test.py")

        methods = [s for s in result.symbols if s.type == "method"]
        for method in methods:
            assert method.parent == "Calculator"

    def test_parse_abstract_class(self, sample_python_complex):
        """Parser handles abstract classes and methods."""
        parser = PythonParser()
        result = parser.parse(sample_python_complex, "test.py")

        base = [s for s in result.symbols if s.name == "BaseProcessor"]
        assert len(base) == 1
        assert base[0].type == "class"


class TestPythonParserImports:
    """Test import extraction."""

    def test_parse_simple_imports(self, sample_python_imports):
        """Parser extracts simple import statements."""
        parser = PythonParser()
        result = parser.parse(sample_python_imports, "test.py")

        import_modules = {i.module for i in result.imports}
        assert "os" in import_modules
        assert "sys" in import_modules

    def test_parse_from_imports(self, sample_python_imports):
        """Parser extracts from ... import statements."""
        parser = PythonParser()
        result = parser.parse(sample_python_imports, "test.py")

        # Find typing import
        typing_imports = [i for i in result.imports if i.module == "typing"]
        assert len(typing_imports) == 1
        assert "Optional" in typing_imports[0].imported_names
        assert "List" in typing_imports[0].imported_names

    def test_parse_from_import_with_multiple_names(self, sample_python_imports):
        """Parser handles from X import a, b, c."""
        parser = PythonParser()
        result = parser.parse(sample_python_imports, "test.py")

        dataclass_import = [i for i in result.imports if i.module == "dataclasses"]
        assert len(dataclass_import) == 1
        assert "dataclass" in dataclass_import[0].imported_names
        assert "field" in dataclass_import[0].imported_names


class TestPythonParserNested:
    """Test nested structure extraction."""

    def test_parse_nested_class(self, sample_python_nested):
        """Parser handles nested classes."""
        parser = PythonParser()
        result = parser.parse(sample_python_nested, "test.py")

        classes = [s for s in result.symbols if s.type == "class"]
        class_names = {c.name for c in classes}

        assert "Outer" in class_names
        assert "Inner" in class_names

    def test_parse_nested_function(self, sample_python_nested):
        """Parser handles nested functions (at least outer one)."""
        parser = PythonParser()
        result = parser.parse(sample_python_nested, "test.py")

        funcs = [s for s in result.symbols if s.type == "function" and s.name == "outer_function"]
        assert len(funcs) == 1


class TestPythonParserEdgeCases:
    """Test edge cases and error handling."""

    def test_parse_empty_file(self):
        """Parser handles empty files."""
        parser = PythonParser()
        result = parser.parse("", "empty.py")

        assert result.symbols == []
        assert result.imports == []
        assert result.errors == []

    def test_parse_syntax_error(self):
        """Parser handles files with syntax errors gracefully."""
        parser = PythonParser()
        code = "def broken(\n  # missing close paren and body"
        result = parser.parse(code, "broken.py")

        # Should not crash, may have partial results or errors
        assert result is not None

    def test_parse_only_comments(self):
        """Parser handles files with only comments."""
        parser = PythonParser()
        code = "# Just a comment\n# Another comment"
        result = parser.parse(code, "comments.py")

        assert result.symbols == []

    def test_parse_preserves_line_numbers(self, sample_python_complex):
        """Parser correctly tracks line numbers."""
        parser = PythonParser()
        result = parser.parse(sample_python_complex, "test.py")

        # CONSTANT_VALUE should be near the end
        constants = [s for s in result.symbols if s.name == "CONSTANT_VALUE"]
        if constants:  # Constants are optional to extract
            assert constants[0].line_start > 30

    def test_qualified_name_for_methods(self, sample_python_class):
        """Methods have qualified names like ClassName.method_name."""
        parser = PythonParser()
        result = parser.parse(sample_python_class, "test.py")

        methods = [s for s in result.symbols if s.type == "method"]
        for method in methods:
            assert method.qualified_name == f"Calculator.{method.name}"


class TestPythonParserFilesParsed:
    """Test parse result metadata."""

    def test_files_parsed_count(self, sample_python_simple):
        """Parse result includes file count."""
        parser = PythonParser()
        result = parser.parse(sample_python_simple, "test.py")

        assert result.files_parsed == 1

    def test_parse_multiple_preserves_file_path(self):
        """Each symbol has correct file_path."""
        parser = PythonParser()

        code1 = "def func1(): pass"
        code2 = "def func2(): pass"

        result1 = parser.parse(code1, "file1.py")
        result2 = parser.parse(code2, "file2.py")

        assert result1.symbols[0].file_path == "file1.py"
        assert result2.symbols[0].file_path == "file2.py"
