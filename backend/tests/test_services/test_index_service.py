"""Tests for the IndexService.

Tests the ability to:
- Build a symbol table from parsed code
- Query symbols by name
- Query symbols by type
- Track file dependencies
- Track callers/callees (when available)
"""

import pytest
from app.parsers.python_parser import PythonParser, Symbol, Import, ParseResult, FunctionCall
from app.services.index_service import IndexService, CodeIndex


class TestIndexServiceBuildIndex:
    """Test building an index from parse results."""

    def test_build_index_empty(self):
        """Building index from empty parse result."""
        service = IndexService()
        parse_result = ParseResult()

        index = service.build_index(parse_result)

        assert index.total_symbols == 0
        assert index.total_files == 0
        assert index.total_classes == 0
        assert index.total_functions == 0

    def test_build_index_with_symbols(self):
        """Building index populates symbol table."""
        service = IndexService()

        symbols = [
            Symbol(
                name="Calculator",
                type="class",
                file_path="calc.py",
                line_start=1,
                line_end=20,
                qualified_name="Calculator",
            ),
            Symbol(
                name="add",
                type="method",
                file_path="calc.py",
                line_start=5,
                line_end=8,
                parent="Calculator",
                qualified_name="Calculator.add",
            ),
        ]
        parse_result = ParseResult(symbols=symbols, files_parsed=1)

        index = service.build_index(parse_result)

        assert index.total_symbols == 2
        assert index.total_classes == 1
        assert index.total_functions == 1
        assert "Calculator" in index.symbol_table
        assert "add" in index.symbol_table

    def test_build_index_counts_files(self):
        """Index correctly counts unique files."""
        service = IndexService()

        symbols = [
            Symbol(name="func1", type="function", file_path="file1.py",
                   line_start=1, line_end=5, qualified_name="func1"),
            Symbol(name="func2", type="function", file_path="file1.py",
                   line_start=7, line_end=10, qualified_name="func2"),
            Symbol(name="func3", type="function", file_path="file2.py",
                   line_start=1, line_end=5, qualified_name="func3"),
        ]
        parse_result = ParseResult(symbols=symbols)

        index = service.build_index(parse_result)

        assert index.total_files == 2

    def test_build_index_file_symbols(self):
        """Index groups symbols by file."""
        service = IndexService()

        symbols = [
            Symbol(name="func1", type="function", file_path="file1.py",
                   line_start=1, line_end=5, qualified_name="func1"),
            Symbol(name="func2", type="function", file_path="file1.py",
                   line_start=7, line_end=10, qualified_name="func2"),
            Symbol(name="func3", type="function", file_path="file2.py",
                   line_start=1, line_end=5, qualified_name="func3"),
        ]
        parse_result = ParseResult(symbols=symbols)

        index = service.build_index(parse_result)

        assert len(index.file_symbols["file1.py"]) == 2
        assert len(index.file_symbols["file2.py"]) == 1


class TestIndexServiceWithParser:
    """Test index service integration with Python parser."""

    @pytest.fixture
    def parsed_code(self, sample_python_complex):
        """Parse complex sample and return result."""
        parser = PythonParser()
        return parser.parse(sample_python_complex, "complex.py")

    def test_integration_with_parser(self, parsed_code):
        """Index service works with real parser output."""
        service = IndexService()
        index = service.build_index(parsed_code)

        assert index.total_symbols > 0
        assert index.total_classes > 0
        assert index.total_functions > 0

    def test_find_symbol_exact(self, parsed_code):
        """Find symbol by exact name."""
        service = IndexService()
        index = service.build_index(parsed_code)

        results = service.find_symbol(index, "TextProcessor", exact=True)

        assert len(results) == 1
        assert results[0].name == "TextProcessor"
        assert results[0].type == "class"

    def test_find_symbol_partial(self, parsed_code):
        """Find symbol by partial name."""
        service = IndexService()
        index = service.build_index(parsed_code)

        results = service.find_symbol(index, "processor", exact=False)

        # Should match TextProcessor, BaseProcessor, create_processor
        names = {s.name for s in results}
        assert "TextProcessor" in names
        assert "BaseProcessor" in names

    def test_find_symbol_by_type_class(self, parsed_code):
        """Find all classes."""
        service = IndexService()
        index = service.build_index(parsed_code)

        results = service.find_symbol_by_type(index, "class")

        names = {s.name for s in results}
        assert "BaseProcessor" in names
        assert "TextProcessor" in names

    def test_find_symbol_by_type_function(self, parsed_code):
        """Find all functions."""
        service = IndexService()
        index = service.build_index(parsed_code)

        results = service.find_symbol_by_type(index, "function")

        names = {s.name for s in results}
        assert "create_processor" in names
        assert "async_process" in names


class TestIndexServiceQueries:
    """Test various query methods."""

    @pytest.fixture
    def sample_index(self):
        """Create a sample index for testing."""
        service = IndexService()

        symbols = [
            Symbol(
                name="UserService",
                type="class",
                file_path="services/user.py",
                line_start=1,
                line_end=50,
                qualified_name="UserService",
            ),
            Symbol(
                name="create_user",
                type="method",
                file_path="services/user.py",
                line_start=10,
                line_end=20,
                parent="UserService",
                qualified_name="UserService.create_user",
            ),
            Symbol(
                name="get_user",
                type="method",
                file_path="services/user.py",
                line_start=22,
                line_end=30,
                parent="UserService",
                qualified_name="UserService.get_user",
            ),
            Symbol(
                name="main",
                type="function",
                file_path="app.py",
                line_start=1,
                line_end=10,
                qualified_name="main",
            ),
        ]

        imports = [
            Import(
                file_path="app.py",
                line=1,
                module="services.user",
                is_from_import=True,
                imported_names=["UserService"],
            ),
        ]

        calls = [
            FunctionCall(
                file_path="app.py",
                line=5,
                caller="main",
                callee="UserService.create_user",
            ),
        ]

        parse_result = ParseResult(
            symbols=symbols,
            imports=imports,
            calls=calls,
            files_parsed=2,
        )

        return service.build_index(parse_result)

    def test_get_file_context(self, sample_index):
        """Get context for a file."""
        service = IndexService()
        context = service.get_file_context(sample_index, "services/user.py")

        assert "file_path" in context
        assert len(context["symbols"]) == 3  # UserService + 2 methods
        assert context["file_path"] == "services/user.py"

    def test_search_symbols_with_type_filter(self, sample_index):
        """Search with type filter."""
        service = IndexService()

        results = service.search_symbols(sample_index, "user", types=["method"])

        names = {s.name for s in results}
        assert "create_user" in names
        assert "get_user" in names
        assert "UserService" not in names  # Class, not method

    def test_search_symbols_with_file_filter(self, sample_index):
        """Search with file pattern filter."""
        service = IndexService()

        results = service.search_symbols(
            sample_index,
            "",
            file_pattern="services/"
        )

        # All results should be from services/
        for result in results:
            assert "services/" in result.file_path

    def test_find_callers(self, sample_index):
        """Find functions calling a given function."""
        service = IndexService()

        callers = service.find_callers(sample_index, "UserService.create_user")

        assert "main" in callers

    def test_find_callees(self, sample_index):
        """Find functions called by a given function."""
        service = IndexService()

        callees = service.find_callees(sample_index, "main")

        assert "UserService.create_user" in callees


class TestIndexServiceEntryPoints:
    """Test entry point detection."""

    def test_get_entry_points_main(self):
        """Detect main function as entry point."""
        service = IndexService()

        symbols = [
            Symbol(name="main", type="function", file_path="app.py",
                   line_start=1, line_end=10, qualified_name="main"),
            Symbol(name="helper", type="function", file_path="app.py",
                   line_start=12, line_end=20, qualified_name="helper"),
        ]
        parse_result = ParseResult(symbols=symbols)
        index = service.build_index(parse_result)

        entry_points = service.get_entry_points(index)

        entry_names = {ep.name for ep in entry_points}
        assert "main" in entry_names

    def test_get_entry_points_handler(self):
        """Detect handler functions as entry points."""
        service = IndexService()

        symbols = [
            Symbol(name="handle_request", type="function", file_path="api.py",
                   line_start=1, line_end=10, qualified_name="handle_request"),
            Symbol(name="process_data", type="function", file_path="api.py",
                   line_start=12, line_end=20, qualified_name="process_data"),
        ]
        parse_result = ParseResult(symbols=symbols)
        index = service.build_index(parse_result)

        entry_points = service.get_entry_points(index)

        entry_names = {ep.name for ep in entry_points}
        assert "handle_request" in entry_names


class TestIndexServiceTopLevelSymbols:
    """Test top-level symbol ranking."""

    def test_get_top_level_symbols(self):
        """Get most important symbols."""
        service = IndexService()

        symbols = [
            Symbol(name="BigClass", type="class", file_path="big.py",
                   line_start=1, line_end=100, qualified_name="BigClass",
                   children=[
                       Symbol(name="m1", type="method", file_path="big.py",
                              line_start=5, line_end=10, parent="BigClass",
                              qualified_name="BigClass.m1"),
                       Symbol(name="m2", type="method", file_path="big.py",
                              line_start=12, line_end=20, parent="BigClass",
                              qualified_name="BigClass.m2"),
                   ]),
            Symbol(name="SmallFunc", type="function", file_path="small.py",
                   line_start=1, line_end=5, qualified_name="SmallFunc"),
        ]
        # Add children as top-level symbols too (they get indexed)
        symbols.extend(symbols[0].children)

        parse_result = ParseResult(symbols=symbols)
        index = service.build_index(parse_result)

        top_symbols = service.get_top_level_symbols(index, limit=10)

        # BigClass should be included (has more methods)
        names = {s.name for s in top_symbols}
        assert "BigClass" in names


class TestIndexServiceDependencies:
    """Test dependency tracking."""

    def test_find_dependencies_empty(self):
        """File with no imports has no dependencies."""
        service = IndexService()

        symbols = [
            Symbol(name="func", type="function", file_path="test.py",
                   line_start=1, line_end=5, qualified_name="func"),
        ]
        parse_result = ParseResult(symbols=symbols)
        index = service.build_index(parse_result)

        deps = service.find_dependencies(index, "test.py")

        assert deps == []

    def test_find_dependents_empty(self):
        """File not imported by anything."""
        service = IndexService()

        symbols = [
            Symbol(name="func", type="function", file_path="test.py",
                   line_start=1, line_end=5, qualified_name="func"),
        ]
        parse_result = ParseResult(symbols=symbols)
        index = service.build_index(parse_result)

        dependents = service.find_dependents(index, "test.py")

        assert dependents == []
