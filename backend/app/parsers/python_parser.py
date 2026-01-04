"""Python parser using tree-sitter for AST-based code analysis.

Extracts:
- Functions (with signatures, docstrings, bodies)
- Classes (with methods as children)
- Imports (regular and from imports)
- Handles nested structures
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Symbol:
    """A code symbol (function, class, method, etc.)."""

    name: str
    type: str  # function, class, method, variable
    file_path: str
    line_start: int
    line_end: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    body: Optional[str] = None
    parent: Optional[str] = None
    qualified_name: Optional[str] = None
    children: list["Symbol"] = field(default_factory=list)
    visibility: str = "public"  # public, private, protected

    def __post_init__(self):
        if self.qualified_name is None:
            if self.parent:
                self.qualified_name = f"{self.parent}.{self.name}"
            else:
                self.qualified_name = self.name


@dataclass
class Import:
    """An import statement."""

    file_path: str
    line: int
    module: str
    alias: Optional[str] = None
    is_from_import: bool = False
    imported_names: list[str] = field(default_factory=list)


@dataclass
class FunctionCall:
    """A function/method call."""
    file_path: str
    line: int
    caller: str  # Qualified name of calling function
    callee: str  # What's being called


@dataclass
class ParseResult:
    """Result of parsing a file or repository."""

    symbols: list[Symbol] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    calls: list[FunctionCall] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    files_parsed: int = 1


class PythonParser:
    """Parser for Python code using tree-sitter."""

    def __init__(self):
        """Initialize the parser with tree-sitter."""
        self._parser = None
        self._language = None
        self._init_parser()

    def _init_parser(self):
        """Initialize tree-sitter parser for Python."""
        try:
            import tree_sitter_python as tspython
            from tree_sitter import Language, Parser

            self._language = Language(tspython.language())
            self._parser = Parser(self._language)
            logger.info("Initialized tree-sitter Python parser")
        except ImportError as e:
            logger.warning(f"tree-sitter not available: {e}")
            self._parser = None
        except Exception as e:
            logger.error(f"Failed to initialize tree-sitter: {e}")
            self._parser = None

    def parse(self, code: str, file_path: str) -> ParseResult:
        """
        Parse Python code and extract symbols and imports.

        Args:
            code: Python source code
            file_path: Path to the file (for metadata)

        Returns:
            ParseResult with symbols, imports, and any errors
        """
        result = ParseResult(files_parsed=1)

        if not code.strip():
            return result

        if not self._parser:
            # Fallback to regex-based parsing
            return self._parse_with_regex(code, file_path)

        try:
            tree = self._parser.parse(bytes(code, "utf-8"))
            root = tree.root_node

            # Extract imports
            result.imports = self._extract_imports(root, code, file_path)

            # Extract symbols (functions, classes)
            result.symbols = self._extract_symbols(root, code, file_path)

        except Exception as e:
            logger.error(f"Parse error for {file_path}: {e}")
            result.errors.append(str(e))

        return result

    def _extract_imports(self, root, code: str, file_path: str) -> list[Import]:
        """Extract all import statements."""
        imports = []

        def find_imports(node):
            if node.type == "import_statement":
                # import x, y, z
                for child in node.children:
                    if child.type == "dotted_name":
                        module = self._get_node_text(child, code)
                        imports.append(Import(
                            file_path=file_path,
                            line=node.start_point[0] + 1,
                            module=module,
                            is_from_import=False,
                        ))
                    elif child.type == "aliased_import":
                        name_node = child.child_by_field_name("name")
                        alias_node = child.child_by_field_name("alias")
                        if name_node:
                            module = self._get_node_text(name_node, code)
                            alias = self._get_node_text(alias_node, code) if alias_node else None
                            imports.append(Import(
                                file_path=file_path,
                                line=node.start_point[0] + 1,
                                module=module,
                                alias=alias,
                                is_from_import=False,
                            ))

            elif node.type == "import_from_statement":
                # from x import y, z
                module_node = node.child_by_field_name("module_name")
                module = self._get_node_text(module_node, code) if module_node else ""

                imported_names = []
                for child in node.children:
                    if child.type == "dotted_name" and child != module_node:
                        imported_names.append(self._get_node_text(child, code))
                    elif child.type == "aliased_import":
                        name_node = child.child_by_field_name("name")
                        if name_node:
                            imported_names.append(self._get_node_text(name_node, code))

                if module or imported_names:
                    imports.append(Import(
                        file_path=file_path,
                        line=node.start_point[0] + 1,
                        module=module,
                        is_from_import=True,
                        imported_names=imported_names,
                    ))

            for child in node.children:
                find_imports(child)

        find_imports(root)
        return imports

    def _extract_symbols(
        self,
        root,
        code: str,
        file_path: str,
        parent_name: Optional[str] = None
    ) -> list[Symbol]:
        """Extract all symbols (functions, classes, etc.)."""
        symbols = []

        def process_node(node, parent=None):
            if node.type == "function_definition":
                symbol = self._extract_function(node, code, file_path, parent)
                symbols.append(symbol)

            elif node.type == "class_definition":
                symbol = self._extract_class(node, code, file_path, parent)
                symbols.append(symbol)

                # Process class body for methods
                body_node = node.child_by_field_name("body")
                if body_node:
                    for child in body_node.children:
                        if child.type == "function_definition":
                            method = self._extract_function(
                                child, code, file_path, symbol.name, is_method=True
                            )
                            symbol.children.append(method)
                            symbols.append(method)
                        elif child.type == "class_definition":
                            # Nested class
                            nested_class = self._extract_class(child, code, file_path, symbol.name)
                            symbol.children.append(nested_class)
                            symbols.append(nested_class)

            elif node.type == "expression_statement":
                # Check for module-level assignments (constants)
                for child in node.children:
                    if child.type == "assignment":
                        left = child.child_by_field_name("left")
                        if left and left.type == "identifier":
                            name = self._get_node_text(left, code)
                            # Only capture UPPER_CASE names as constants
                            if name.isupper():
                                symbols.append(Symbol(
                                    name=name,
                                    type="variable",
                                    file_path=file_path,
                                    line_start=node.start_point[0] + 1,
                                    line_end=node.end_point[0] + 1,
                                    body=self._get_node_text(node, code),
                                ))

            # Continue traversing for top-level definitions
            if node.type in ("module", "block"):
                for child in node.children:
                    process_node(child, parent)

        process_node(root)
        return symbols

    def _extract_function(
        self,
        node,
        code: str,
        file_path: str,
        parent: Optional[str] = None,
        is_method: bool = False
    ) -> Symbol:
        """Extract a function or method definition."""
        name_node = node.child_by_field_name("name")
        name = self._get_node_text(name_node, code) if name_node else "unknown"

        # Get parameters for signature
        params_node = node.child_by_field_name("parameters")
        params = self._get_node_text(params_node, code) if params_node else "()"

        # Get return type if present
        return_type_node = node.child_by_field_name("return_type")
        return_type = ""
        if return_type_node:
            return_type = " -> " + self._get_node_text(return_type_node, code)

        signature = f"def {name}{params}{return_type}"

        # Get docstring
        body_node = node.child_by_field_name("body")
        docstring = self._extract_docstring(body_node, code)

        # Get full body
        body = self._get_node_text(node, code)

        # Determine visibility
        visibility = "public"
        if name.startswith("__") and name.endswith("__"):
            visibility = "magic"
        elif name.startswith("__"):
            visibility = "private"
        elif name.startswith("_"):
            visibility = "protected"

        return Symbol(
            name=name,
            type="method" if is_method else "function",
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=signature,
            docstring=docstring,
            body=body,
            parent=parent,
            visibility=visibility,
        )

    def _extract_class(
        self,
        node,
        code: str,
        file_path: str,
        parent: Optional[str] = None
    ) -> Symbol:
        """Extract a class definition."""
        name_node = node.child_by_field_name("name")
        name = self._get_node_text(name_node, code) if name_node else "unknown"

        # Get base classes
        superclass_node = node.child_by_field_name("superclasses")
        bases = ""
        if superclass_node:
            bases = self._get_node_text(superclass_node, code)

        signature = f"class {name}{bases}:" if bases else f"class {name}:"

        # Get docstring
        body_node = node.child_by_field_name("body")
        docstring = self._extract_docstring(body_node, code)

        # Get full body
        body = self._get_node_text(node, code)

        return Symbol(
            name=name,
            type="class",
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=signature,
            docstring=docstring,
            body=body,
            parent=parent,
        )

    def _extract_docstring(self, body_node, code: str) -> Optional[str]:
        """Extract docstring from a function/class body."""
        if not body_node:
            return None

        for child in body_node.children:
            if child.type == "expression_statement":
                for sub in child.children:
                    if sub.type == "string":
                        text = self._get_node_text(sub, code)
                        # Remove quotes and clean up
                        if text.startswith('"""') or text.startswith("'''"):
                            return text[3:-3].strip()
                        elif text.startswith('"') or text.startswith("'"):
                            return text[1:-1].strip()
            # Only first statement can be docstring
            break

        return None

    def _get_node_text(self, node, code: str) -> str:
        """Get the text content of a node."""
        if node is None:
            return ""
        return code[node.start_byte:node.end_byte]

    def _parse_with_regex(self, code: str, file_path: str) -> ParseResult:
        """Fallback regex-based parsing when tree-sitter is unavailable."""
        import re

        result = ParseResult(files_parsed=1)
        lines = code.split('\n')

        # Simple regex patterns
        func_pattern = re.compile(r'^(\s*)def\s+(\w+)\s*\([^)]*\)')
        class_pattern = re.compile(r'^(\s*)class\s+(\w+)(?:\([^)]*\))?:')
        import_pattern = re.compile(r'^import\s+(\S+)')
        from_import_pattern = re.compile(r'^from\s+(\S+)\s+import\s+(.+)')

        current_class = None
        current_indent = 0

        for i, line in enumerate(lines):
            line_num = i + 1

            # Check for imports
            match = import_pattern.match(line)
            if match:
                result.imports.append(Import(
                    file_path=file_path,
                    line=line_num,
                    module=match.group(1),
                    is_from_import=False,
                ))
                continue

            match = from_import_pattern.match(line)
            if match:
                names = [n.strip() for n in match.group(2).split(',')]
                result.imports.append(Import(
                    file_path=file_path,
                    line=line_num,
                    module=match.group(1),
                    is_from_import=True,
                    imported_names=names,
                ))
                continue

            # Check for class
            match = class_pattern.match(line)
            if match:
                indent = len(match.group(1))
                name = match.group(2)
                current_class = name
                current_indent = indent
                result.symbols.append(Symbol(
                    name=name,
                    type="class",
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,  # Will be updated later
                ))
                continue

            # Check for function/method
            match = func_pattern.match(line)
            if match:
                indent = len(match.group(1))
                name = match.group(2)

                is_method = current_class and indent > current_indent
                parent = current_class if is_method else None

                result.symbols.append(Symbol(
                    name=name,
                    type="method" if is_method else "function",
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,
                    parent=parent,
                ))

        return result
