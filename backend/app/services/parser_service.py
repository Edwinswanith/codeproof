"""Service for parsing code with tree-sitter AST."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import tree-sitter, gracefully handle if not installed
try:
    import tree_sitter_python
    import tree_sitter_javascript
    import tree_sitter_typescript
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    logger.warning("tree-sitter not installed. Using fallback regex parsing.")


@dataclass
class Symbol:
    """A code symbol (class, function, method, variable)."""
    type: str  # class, function, method, variable, constant, import
    name: str
    qualified_name: str  # e.g., "app.services.UserService.create"
    file_path: str
    line_start: int
    line_end: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    parent: Optional[str] = None
    children: list[str] = field(default_factory=list)
    visibility: Optional[str] = None  # public, private, protected
    body: Optional[str] = None  # Full source code of the symbol


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
    """Complete parse result for a repository."""
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    calls: list[FunctionCall] = field(default_factory=list)
    files_parsed: int = 0
    parse_errors: list[str] = field(default_factory=list)


class ParserService:
    """Service for parsing code with tree-sitter."""

    SUPPORTED_LANGUAGES = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".php": "php",
        ".rb": "ruby",
        ".go": "go",
        ".java": "java",
        ".rs": "rust",
        ".c": "c",
        ".cpp": "cpp",
        ".cs": "c_sharp",
    }

    # Files/dirs to skip
    SKIP_DIRS = {
        "node_modules", ".git", "__pycache__", ".venv", "venv",
        "vendor", "dist", "build", ".next", ".nuxt", "coverage",
        ".pytest_cache", ".mypy_cache", "eggs", ".eggs",
    }
    SKIP_FILES = {".min.js", ".bundle.js", ".map"}

    def __init__(self):
        """Initialize parsers for each language."""
        self.parsers = {}
        
        if TREE_SITTER_AVAILABLE:
            try:
                import tree_sitter
                
                # Initialize Python parser
                self.python_language = tree_sitter.Language(tree_sitter_python.language())
                self.parsers["python"] = tree_sitter.Parser(self.python_language)
                
                # Initialize JavaScript parser
                self.js_language = tree_sitter.Language(tree_sitter_javascript.language())
                self.parsers["javascript"] = tree_sitter.Parser(self.js_language)
                
                # Initialize TypeScript parser
                self.ts_language = tree_sitter.Language(tree_sitter_typescript.language_typescript())
                self.parsers["typescript"] = tree_sitter.Parser(self.ts_language)
                
                logger.info(f"Initialized tree-sitter parsers: {list(self.parsers.keys())}")
            except Exception as e:
                logger.warning(f"Failed to initialize tree-sitter: {e}")

    def parse_repository(self, repo_path: str, coverage_service=None) -> ParseResult:
        """Parse all code files in repository.
        
        Args:
            repo_path: Path to repository
            coverage_service: Optional CoverageService to track coverage
        """
        result = ParseResult()
        
        for root, dirs, files in os.walk(repo_path):
            # Skip unwanted directories
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]
            
            for filename in files:
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, repo_path)
                
                # Check file size for coverage tracking
                file_size = None
                if coverage_service:
                    try:
                        file_size = os.path.getsize(file_path)
                    except OSError:
                        pass
                
                # Check if file should be skipped
                skip_reason = None
                if coverage_service:
                    skip_reason = coverage_service.should_skip_file(rel_path, file_size)
                    if skip_reason:
                        coverage_service.record_file_skipped(rel_path, skip_reason)
                        continue
                
                # Skip unwanted files
                if any(filename.endswith(skip) for skip in self.SKIP_FILES):
                    if coverage_service:
                        coverage_service.record_file_skipped(rel_path, "minified_or_bundle")
                    continue
                
                ext = os.path.splitext(filename)[1].lower()
                if ext not in self.SUPPORTED_LANGUAGES:
                    if coverage_service and not skip_reason:
                        coverage_service.record_file_skipped(rel_path, "unsupported_language")
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                    
                    language = self.SUPPORTED_LANGUAGES[ext]
                    symbols, imports, calls = self.parse_file(rel_path, content, language)
                    
                    result.symbols.extend(symbols)
                    result.imports.extend(imports)
                    result.calls.extend(calls)
                    result.files_parsed += 1
                    
                    if coverage_service:
                        coverage_service.record_file_parsed(rel_path, language)
                    
                except Exception as e:
                    error_msg = f"{rel_path}: {str(e)}"
                    result.parse_errors.append(error_msg)
                    if coverage_service:
                        coverage_service.record_parse_error(rel_path, str(e))
        
        logger.info(
            f"Parsed {result.files_parsed} files: "
            f"{len(result.symbols)} symbols, {len(result.imports)} imports, "
            f"{len(result.calls)} calls, {len(result.parse_errors)} errors"
        )
        
        return result

    def parse_file(
        self, 
        file_path: str, 
        content: str, 
        language: str
    ) -> tuple[list[Symbol], list[Import], list[FunctionCall]]:
        """Parse a single file."""
        if language == "python":
            return self._parse_python(file_path, content)
        elif language in ("javascript", "typescript"):
            return self._parse_javascript(file_path, content, language)
        else:
            # Fallback to regex-based parsing for unsupported languages
            return self._parse_fallback(file_path, content, language)

    def _parse_python(
        self, 
        file_path: str, 
        content: str
    ) -> tuple[list[Symbol], list[Import], list[FunctionCall]]:
        """Extract symbols from Python AST."""
        symbols = []
        imports = []
        calls = []
        
        if "python" in self.parsers:
            try:
                parser = self.parsers["python"]
                tree = parser.parse(content.encode())
                content_bytes = content.encode()
                
                symbols = self._extract_python_symbols(tree.root_node, content_bytes, file_path)
                imports = self._extract_python_imports(tree.root_node, content_bytes, file_path)
                calls = self._extract_python_calls(tree.root_node, content_bytes, file_path)
                
            except Exception as e:
                logger.warning(f"Tree-sitter parse failed for {file_path}: {e}")
                symbols, imports, calls = self._parse_python_fallback(file_path, content)
        else:
            symbols, imports, calls = self._parse_python_fallback(file_path, content)
        
        return symbols, imports, calls

    def _extract_python_symbols(
        self, 
        node, 
        content_bytes: bytes, 
        file_path: str, 
        parent: Optional[str] = None
    ) -> list[Symbol]:
        """Extract symbols from Python AST node."""
        symbols = []
        
        for child in node.children:
            if child.type == "class_definition":
                # Extract class
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = content_bytes[name_node.start_byte:name_node.end_byte].decode()
                    qualified_name = f"{file_path}:{name}" if not parent else f"{parent}.{name}"
                    
                    # Get body for methods
                    body = child.child_by_field_name("body")
                    methods = []
                    if body:
                        for stmt in body.children:
                            if stmt.type == "function_definition":
                                method_name_node = stmt.child_by_field_name("name")
                                if method_name_node:
                                    method_name = content_bytes[method_name_node.start_byte:method_name_node.end_byte].decode()
                                    methods.append(method_name)
                    
                    # Get docstring
                    docstring = self._extract_python_docstring(body, content_bytes) if body else None
                    
                    # Get class body source
                    body_source = content_bytes[child.start_byte:child.end_byte].decode()
                    
                    symbols.append(Symbol(
                        type="class",
                        name=name,
                        qualified_name=qualified_name,
                        file_path=file_path,
                        line_start=child.start_point[0] + 1,
                        line_end=child.end_point[0] + 1,
                        signature=None,
                        docstring=docstring,
                        parent=parent,
                        children=methods,
                        visibility="public" if not name.startswith("_") else "private",
                        body=body_source,
                    ))
                    
                    # Recursively extract methods
                    if body:
                        symbols.extend(self._extract_python_symbols(body, content_bytes, file_path, qualified_name))
            
            elif child.type == "function_definition":
                # Extract function/method
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = content_bytes[name_node.start_byte:name_node.end_byte].decode()
                    qualified_name = f"{file_path}:{name}" if not parent else f"{parent}.{name}"
                    
                    # Get signature
                    params_node = child.child_by_field_name("parameters")
                    params = ""
                    if params_node:
                        params = content_bytes[params_node.start_byte:params_node.end_byte].decode()
                    
                    # Get return type
                    return_type = child.child_by_field_name("return_type")
                    return_str = ""
                    if return_type:
                        return_str = " -> " + content_bytes[return_type.start_byte:return_type.end_byte].decode()
                    
                    signature = f"def {name}{params}{return_str}"
                    
                    # Get docstring
                    body = child.child_by_field_name("body")
                    docstring = self._extract_python_docstring(body, content_bytes) if body else None
                    
                    # Get function body
                    body_source = content_bytes[child.start_byte:child.end_byte].decode()
                    
                    symbol_type = "method" if parent else "function"
                    visibility = "public"
                    if name.startswith("__") and name.endswith("__"):
                        visibility = "magic"
                    elif name.startswith("_"):
                        visibility = "private"
                    
                    symbols.append(Symbol(
                        type=symbol_type,
                        name=name,
                        qualified_name=qualified_name,
                        file_path=file_path,
                        line_start=child.start_point[0] + 1,
                        line_end=child.end_point[0] + 1,
                        signature=signature,
                        docstring=docstring,
                        parent=parent,
                        children=[],
                        visibility=visibility,
                        body=body_source,
                    ))
            
            else:
                # Recurse into other nodes
                symbols.extend(self._extract_python_symbols(child, content_bytes, file_path, parent))
        
        return symbols

    def _extract_python_docstring(self, body_node, content_bytes: bytes) -> Optional[str]:
        """Extract docstring from function/class body."""
        if not body_node or not body_node.children:
            return None
        
        first_stmt = body_node.children[0]
        if first_stmt.type == "expression_statement":
            expr = first_stmt.children[0] if first_stmt.children else None
            if expr and expr.type == "string":
                docstring = content_bytes[expr.start_byte:expr.end_byte].decode()
                # Clean up quotes
                if docstring.startswith('"""') or docstring.startswith("'''"):
                    docstring = docstring[3:-3]
                elif docstring.startswith('"') or docstring.startswith("'"):
                    docstring = docstring[1:-1]
                return docstring.strip()
        
        return None

    def _extract_python_imports(
        self, 
        node, 
        content_bytes: bytes, 
        file_path: str
    ) -> list[Import]:
        """Extract imports from Python AST."""
        imports = []
        
        for child in node.children:
            if child.type == "import_statement":
                # import x, y, z
                for name_node in child.children:
                    if name_node.type == "dotted_name":
                        module = content_bytes[name_node.start_byte:name_node.end_byte].decode()
                        imports.append(Import(
                            file_path=file_path,
                            line=child.start_point[0] + 1,
                            module=module,
                            alias=None,
                            is_from_import=False,
                        ))
                    elif name_node.type == "aliased_import":
                        name = name_node.child_by_field_name("name")
                        alias = name_node.child_by_field_name("alias")
                        if name:
                            module = content_bytes[name.start_byte:name.end_byte].decode()
                            alias_str = content_bytes[alias.start_byte:alias.end_byte].decode() if alias else None
                            imports.append(Import(
                                file_path=file_path,
                                line=child.start_point[0] + 1,
                                module=module,
                                alias=alias_str,
                                is_from_import=False,
                            ))
            
            elif child.type == "import_from_statement":
                # from x import y, z
                module_node = child.child_by_field_name("module_name")
                if module_node:
                    module = content_bytes[module_node.start_byte:module_node.end_byte].decode()
                else:
                    # Handle relative imports
                    module = ""
                
                imported_names = []
                for name_node in child.children:
                    if name_node.type == "dotted_name":
                        imported_names.append(
                            content_bytes[name_node.start_byte:name_node.end_byte].decode()
                        )
                    elif name_node.type == "aliased_import":
                        name = name_node.child_by_field_name("name")
                        if name:
                            imported_names.append(
                                content_bytes[name.start_byte:name.end_byte].decode()
                            )
                
                imports.append(Import(
                    file_path=file_path,
                    line=child.start_point[0] + 1,
                    module=module,
                    alias=None,
                    is_from_import=True,
                    imported_names=imported_names,
                ))
            
            else:
                # Recurse
                imports.extend(self._extract_python_imports(child, content_bytes, file_path))
        
        return imports

    def _extract_python_calls(
        self, 
        node, 
        content_bytes: bytes, 
        file_path: str,
        current_func: Optional[str] = None
    ) -> list[FunctionCall]:
        """Extract function calls from Python AST."""
        calls = []
        
        for child in node.children:
            # Track current function context
            if child.type == "function_definition":
                name_node = child.child_by_field_name("name")
                if name_node:
                    func_name = content_bytes[name_node.start_byte:name_node.end_byte].decode()
                    body = child.child_by_field_name("body")
                    if body:
                        calls.extend(self._extract_python_calls(
                            body, content_bytes, file_path, 
                            f"{file_path}:{func_name}"
                        ))
                continue
            
            elif child.type == "class_definition":
                name_node = child.child_by_field_name("name")
                if name_node:
                    class_name = content_bytes[name_node.start_byte:name_node.end_byte].decode()
                    body = child.child_by_field_name("body")
                    if body:
                        # Process methods inside class
                        for stmt in body.children:
                            if stmt.type == "function_definition":
                                method_name_node = stmt.child_by_field_name("name")
                                if method_name_node:
                                    method_name = content_bytes[method_name_node.start_byte:method_name_node.end_byte].decode()
                                    method_body = stmt.child_by_field_name("body")
                                    if method_body:
                                        calls.extend(self._extract_python_calls(
                                            method_body, content_bytes, file_path,
                                            f"{file_path}:{class_name}.{method_name}"
                                        ))
                continue
            
            elif child.type == "call":
                # Extract call target
                func_node = child.child_by_field_name("function")
                if func_node:
                    callee = content_bytes[func_node.start_byte:func_node.end_byte].decode()
                    calls.append(FunctionCall(
                        file_path=file_path,
                        line=child.start_point[0] + 1,
                        caller=current_func or f"{file_path}:module",
                        callee=callee,
                    ))
            
            # Recurse into other nodes
            calls.extend(self._extract_python_calls(child, content_bytes, file_path, current_func))
        
        return calls

    def _parse_python_fallback(
        self, 
        file_path: str, 
        content: str
    ) -> tuple[list[Symbol], list[Import], list[FunctionCall]]:
        """Fallback regex-based Python parsing."""
        import re
        
        symbols = []
        imports = []
        calls = []
        lines = content.split('\n')
        
        # Extract classes and functions with regex
        class_pattern = re.compile(r'^class\s+(\w+)')
        func_pattern = re.compile(r'^(\s*)def\s+(\w+)\s*\(([^)]*)\)')
        import_pattern = re.compile(r'^import\s+(\S+)')
        from_import_pattern = re.compile(r'^from\s+(\S+)\s+import\s+(.+)')
        
        current_class = None
        
        for i, line in enumerate(lines):
            line_num = i + 1
            
            # Classes
            match = class_pattern.match(line)
            if match:
                name = match.group(1)
                current_class = name
                symbols.append(Symbol(
                    type="class",
                    name=name,
                    qualified_name=f"{file_path}:{name}",
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,
                    visibility="public" if not name.startswith("_") else "private",
                ))
                continue
            
            # Functions/methods
            match = func_pattern.match(line)
            if match:
                indent = match.group(1)
                name = match.group(2)
                params = match.group(3)
                
                if indent and current_class:
                    # Method
                    qualified_name = f"{file_path}:{current_class}.{name}"
                    symbol_type = "method"
                else:
                    # Top-level function
                    qualified_name = f"{file_path}:{name}"
                    symbol_type = "function"
                    current_class = None
                
                symbols.append(Symbol(
                    type=symbol_type,
                    name=name,
                    qualified_name=qualified_name,
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,
                    signature=f"def {name}({params})",
                    parent=f"{file_path}:{current_class}" if current_class and indent else None,
                    visibility="public" if not name.startswith("_") else "private",
                ))
                continue
            
            # Imports
            match = import_pattern.match(line)
            if match:
                imports.append(Import(
                    file_path=file_path,
                    line=line_num,
                    module=match.group(1),
                    is_from_import=False,
                ))
                continue
            
            match = from_import_pattern.match(line)
            if match:
                module = match.group(1)
                names = [n.strip() for n in match.group(2).split(',')]
                imports.append(Import(
                    file_path=file_path,
                    line=line_num,
                    module=module,
                    is_from_import=True,
                    imported_names=names,
                ))
        
        return symbols, imports, calls

    def _parse_javascript(
        self, 
        file_path: str, 
        content: str,
        language: str
    ) -> tuple[list[Symbol], list[Import], list[FunctionCall]]:
        """Extract symbols from JavaScript/TypeScript AST."""
        symbols = []
        imports = []
        calls = []
        
        parser_key = language if language in self.parsers else "javascript"
        
        if parser_key in self.parsers:
            try:
                parser = self.parsers[parser_key]
                tree = parser.parse(content.encode())
                content_bytes = content.encode()
                
                symbols = self._extract_js_symbols(tree.root_node, content_bytes, file_path)
                imports = self._extract_js_imports(tree.root_node, content_bytes, file_path)
                
            except Exception as e:
                logger.warning(f"Tree-sitter parse failed for {file_path}: {e}")
                symbols, imports, calls = self._parse_js_fallback(file_path, content)
        else:
            symbols, imports, calls = self._parse_js_fallback(file_path, content)
        
        return symbols, imports, calls

    def _extract_js_symbols(
        self, 
        node, 
        content_bytes: bytes, 
        file_path: str,
        parent: Optional[str] = None
    ) -> list[Symbol]:
        """Extract symbols from JavaScript AST."""
        symbols = []
        
        for child in node.children:
            # Class declaration
            if child.type == "class_declaration":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = content_bytes[name_node.start_byte:name_node.end_byte].decode()
                    qualified_name = f"{file_path}:{name}"
                    
                    body = child.child_by_field_name("body")
                    methods = []
                    if body:
                        for member in body.children:
                            if member.type == "method_definition":
                                method_name = member.child_by_field_name("name")
                                if method_name:
                                    methods.append(
                                        content_bytes[method_name.start_byte:method_name.end_byte].decode()
                                    )
                    
                    body_source = content_bytes[child.start_byte:child.end_byte].decode()
                    
                    symbols.append(Symbol(
                        type="class",
                        name=name,
                        qualified_name=qualified_name,
                        file_path=file_path,
                        line_start=child.start_point[0] + 1,
                        line_end=child.end_point[0] + 1,
                        children=methods,
                        visibility="public",
                        body=body_source,
                    ))
                    
                    # Extract methods
                    if body:
                        symbols.extend(self._extract_js_symbols(body, content_bytes, file_path, qualified_name))
            
            # Function declaration
            elif child.type in ("function_declaration", "function"):
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = content_bytes[name_node.start_byte:name_node.end_byte].decode()
                    qualified_name = f"{file_path}:{name}" if not parent else f"{parent}.{name}"
                    
                    params = child.child_by_field_name("parameters")
                    params_str = content_bytes[params.start_byte:params.end_byte].decode() if params else "()"
                    
                    body_source = content_bytes[child.start_byte:child.end_byte].decode()
                    
                    symbols.append(Symbol(
                        type="function",
                        name=name,
                        qualified_name=qualified_name,
                        file_path=file_path,
                        line_start=child.start_point[0] + 1,
                        line_end=child.end_point[0] + 1,
                        signature=f"function {name}{params_str}",
                        parent=parent,
                        visibility="public",
                        body=body_source,
                    ))
            
            # Arrow function in variable
            elif child.type == "lexical_declaration" or child.type == "variable_declaration":
                for decl in child.children:
                    if decl.type == "variable_declarator":
                        name_node = decl.child_by_field_name("name")
                        value_node = decl.child_by_field_name("value")
                        if name_node and value_node and value_node.type == "arrow_function":
                            name = content_bytes[name_node.start_byte:name_node.end_byte].decode()
                            qualified_name = f"{file_path}:{name}"
                            
                            params = value_node.child_by_field_name("parameters")
                            if params:
                                params_str = content_bytes[params.start_byte:params.end_byte].decode()
                            else:
                                # Single param without parens
                                params_str = "()"
                            
                            body_source = content_bytes[child.start_byte:child.end_byte].decode()
                            
                            symbols.append(Symbol(
                                type="function",
                                name=name,
                                qualified_name=qualified_name,
                                file_path=file_path,
                                line_start=child.start_point[0] + 1,
                                line_end=child.end_point[0] + 1,
                                signature=f"const {name} = {params_str} =>",
                                visibility="public",
                                body=body_source,
                            ))
            
            # Method definition
            elif child.type == "method_definition":
                name_node = child.child_by_field_name("name")
                if name_node:
                    name = content_bytes[name_node.start_byte:name_node.end_byte].decode()
                    qualified_name = f"{parent}.{name}" if parent else f"{file_path}:{name}"
                    
                    params = child.child_by_field_name("parameters")
                    params_str = content_bytes[params.start_byte:params.end_byte].decode() if params else "()"
                    
                    body_source = content_bytes[child.start_byte:child.end_byte].decode()
                    
                    symbols.append(Symbol(
                        type="method",
                        name=name,
                        qualified_name=qualified_name,
                        file_path=file_path,
                        line_start=child.start_point[0] + 1,
                        line_end=child.end_point[0] + 1,
                        signature=f"{name}{params_str}",
                        parent=parent,
                        visibility="public",
                        body=body_source,
                    ))
            
            else:
                # Recurse
                symbols.extend(self._extract_js_symbols(child, content_bytes, file_path, parent))
        
        return symbols

    def _extract_js_imports(
        self, 
        node, 
        content_bytes: bytes, 
        file_path: str
    ) -> list[Import]:
        """Extract imports from JavaScript AST."""
        imports = []
        
        for child in node.children:
            if child.type == "import_statement":
                source = child.child_by_field_name("source")
                if source:
                    module = content_bytes[source.start_byte:source.end_byte].decode()
                    module = module.strip("'\"")
                    
                    imported_names = []
                    for c in child.children:
                        if c.type == "import_clause":
                            for ic in c.children:
                                if ic.type == "identifier":
                                    imported_names.append(
                                        content_bytes[ic.start_byte:ic.end_byte].decode()
                                    )
                                elif ic.type == "named_imports":
                                    for spec in ic.children:
                                        if spec.type == "import_specifier":
                                            name = spec.child_by_field_name("name")
                                            if name:
                                                imported_names.append(
                                                    content_bytes[name.start_byte:name.end_byte].decode()
                                                )
                    
                    imports.append(Import(
                        file_path=file_path,
                        line=child.start_point[0] + 1,
                        module=module,
                        is_from_import=True,
                        imported_names=imported_names,
                    ))
            else:
                imports.extend(self._extract_js_imports(child, content_bytes, file_path))
        
        return imports

    def _parse_js_fallback(
        self, 
        file_path: str, 
        content: str
    ) -> tuple[list[Symbol], list[Import], list[FunctionCall]]:
        """Fallback regex-based JavaScript parsing."""
        import re
        
        symbols = []
        imports = []
        calls = []
        lines = content.split('\n')
        
        class_pattern = re.compile(r'class\s+(\w+)')
        func_pattern = re.compile(r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\()')
        import_pattern = re.compile(r"import\s+.*\s+from\s+['\"]([^'\"]+)['\"]")
        
        for i, line in enumerate(lines):
            line_num = i + 1
            
            match = class_pattern.search(line)
            if match:
                name = match.group(1)
                symbols.append(Symbol(
                    type="class",
                    name=name,
                    qualified_name=f"{file_path}:{name}",
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,
                    visibility="public",
                ))
            
            match = func_pattern.search(line)
            if match:
                name = match.group(1) or match.group(2)
                if name:
                    symbols.append(Symbol(
                        type="function",
                        name=name,
                        qualified_name=f"{file_path}:{name}",
                        file_path=file_path,
                        line_start=line_num,
                        line_end=line_num,
                        visibility="public",
                    ))
            
            match = import_pattern.search(line)
            if match:
                imports.append(Import(
                    file_path=file_path,
                    line=line_num,
                    module=match.group(1),
                    is_from_import=True,
                ))
        
        return symbols, imports, calls

    def _parse_fallback(
        self, 
        file_path: str, 
        content: str,
        language: str
    ) -> tuple[list[Symbol], list[Import], list[FunctionCall]]:
        """Generic fallback for unsupported languages."""
        import re
        
        symbols = []
        imports = []
        lines = content.split('\n')
        
        # Very basic patterns that work across languages
        class_pattern = re.compile(r'class\s+(\w+)')
        func_pattern = re.compile(r'(?:function|def|func|fn)\s+(\w+)')
        
        for i, line in enumerate(lines):
            line_num = i + 1
            
            match = class_pattern.search(line)
            if match:
                name = match.group(1)
                symbols.append(Symbol(
                    type="class",
                    name=name,
                    qualified_name=f"{file_path}:{name}",
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,
                ))
            
            match = func_pattern.search(line)
            if match:
                name = match.group(1)
                symbols.append(Symbol(
                    type="function",
                    name=name,
                    qualified_name=f"{file_path}:{name}",
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,
                ))
        
        return symbols, imports, []
