"""Service for building and querying code indexes."""

import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from app.parsers.python_parser import Symbol, Import, FunctionCall, ParseResult

logger = logging.getLogger(__name__)


@dataclass
class CodeIndex:
    """Complete index of a codebase."""

    # Symbol lookup: name -> list of symbols with that name
    symbol_table: dict[str, list[Symbol]] = field(default_factory=lambda: defaultdict(list))

    # Dependency graph: file -> files it imports
    dependencies: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    # Reverse dependencies: file -> files that import it
    reverse_dependencies: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    # Call graph: function qualified_name -> functions it calls
    call_graph: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    # Reverse call graph: function -> functions that call it
    callers: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    # File -> symbols in that file
    file_symbols: dict[str, list[Symbol]] = field(default_factory=lambda: defaultdict(list))

    # Quick stats
    total_files: int = 0
    total_symbols: int = 0
    total_functions: int = 0
    total_classes: int = 0


class IndexService:
    """Service for building and querying code indexes."""

    def build_index(self, parse_result: ParseResult, repo_path: str = "") -> CodeIndex:
        """Build searchable index from parse result."""
        index = CodeIndex()

        # Build symbol table
        for symbol in parse_result.symbols:
            # Index by name
            index.symbol_table[symbol.name].append(symbol)
            
            # Index by file
            index.file_symbols[symbol.file_path].append(symbol)
            
            # Count by type
            if symbol.type == "class":
                index.total_classes += 1
            elif symbol.type in ("function", "method"):
                index.total_functions += 1

        index.total_symbols = len(parse_result.symbols)

        # Build dependency graph
        for imp in parse_result.imports:
            resolved_path = self._resolve_import(imp, repo_path, parse_result)
            if resolved_path:
                index.dependencies[imp.file_path].append(resolved_path)
                index.reverse_dependencies[resolved_path].append(imp.file_path)

        # Build call graph
        for call in parse_result.calls:
            # Try to resolve callee to qualified name
            resolved_callee = self._resolve_call(call, index)
            index.call_graph[call.caller].append(resolved_callee)
            index.callers[resolved_callee].append(call.caller)

        # Count unique files
        all_files = set()
        for symbol in parse_result.symbols:
            all_files.add(symbol.file_path)
        index.total_files = len(all_files)

        logger.info(
            f"Built index: {index.total_files} files, {index.total_symbols} symbols, "
            f"{index.total_classes} classes, {index.total_functions} functions"
        )

        return index

    def _resolve_import(
        self, 
        imp: Import, 
        repo_path: str,
        parse_result: ParseResult
    ) -> Optional[str]:
        """Resolve import to actual file path."""
        if not imp.module:
            return None

        # Get all known file paths
        known_files = set(s.file_path for s in parse_result.symbols)

        # Python-style resolution
        module_path = imp.module.replace(".", "/")

        # Try as file
        candidates = [
            f"{module_path}.py",
            f"{module_path}/__init__.py",
            f"{module_path}.js",
            f"{module_path}.ts",
            f"{module_path}.tsx",
            f"{module_path}/index.js",
            f"{module_path}/index.ts",
            f"{module_path}/index.tsx",
        ]

        for candidate in candidates:
            if candidate in known_files:
                return candidate

        # Try with src/ prefix (common in JS projects)
        for candidate in candidates:
            src_candidate = f"src/{candidate}"
            if src_candidate in known_files:
                return src_candidate

        # Check if it's a relative import
        if imp.module.startswith("."):
            # Relative to current file's directory
            current_dir = os.path.dirname(imp.file_path)
            rel_path = imp.module.lstrip(".")
            rel_path = rel_path.replace(".", "/")
            
            for ext in [".py", ".js", ".ts", ".tsx", "/index.js", "/index.ts"]:
                candidate = os.path.normpath(os.path.join(current_dir, rel_path + ext))
                if candidate in known_files:
                    return candidate

        return None  # External dependency

    def _resolve_call(self, call: FunctionCall, index: CodeIndex) -> str:
        """Try to resolve a function call to a qualified name."""
        callee = call.callee

        # Handle method calls (obj.method)
        if "." in callee:
            parts = callee.split(".")
            method_name = parts[-1]
            
            # Try to find the method in symbol table
            if method_name in index.symbol_table:
                symbols = index.symbol_table[method_name]
                # Prefer methods over functions
                for sym in symbols:
                    if sym.type == "method":
                        return sym.qualified_name
                if symbols:
                    return symbols[0].qualified_name

        # Try direct lookup
        if callee in index.symbol_table:
            symbols = index.symbol_table[callee]
            if symbols:
                return symbols[0].qualified_name

        # Can't resolve - return as-is
        return callee

    def find_symbol(self, index: CodeIndex, name: str, exact: bool = False) -> list[Symbol]:
        """Find symbols by name (exact or partial match)."""
        if exact:
            return index.symbol_table.get(name, [])

        # Partial match
        results = []
        name_lower = name.lower()
        for sym_name, symbols in index.symbol_table.items():
            if name_lower in sym_name.lower():
                results.extend(symbols)

        return results

    def find_symbol_by_type(
        self, 
        index: CodeIndex, 
        symbol_type: str,
        name_pattern: Optional[str] = None
    ) -> list[Symbol]:
        """Find symbols by type (class, function, method)."""
        results = []
        for symbols in index.symbol_table.values():
            for sym in symbols:
                if sym.type == symbol_type:
                    if name_pattern is None or name_pattern.lower() in sym.name.lower():
                        results.append(sym)
        return results

    def find_callers(self, index: CodeIndex, function_name: str) -> list[str]:
        """Find all functions that call the given function."""
        # Try exact match first
        if function_name in index.callers:
            return list(set(index.callers[function_name]))

        # Try partial match on qualified names
        results = []
        for callee, callers in index.callers.items():
            if function_name in callee:
                results.extend(callers)

        return list(set(results))

    def find_callees(self, index: CodeIndex, function_name: str) -> list[str]:
        """Find all functions called by the given function."""
        # Try exact match first
        if function_name in index.call_graph:
            return list(set(index.call_graph[function_name]))

        # Try partial match
        results = []
        for caller, callees in index.call_graph.items():
            if function_name in caller:
                results.extend(callees)

        return list(set(results))

    def find_dependencies(self, index: CodeIndex, file_path: str) -> list[str]:
        """Find all files imported by the given file."""
        return index.dependencies.get(file_path, [])

    def find_dependents(self, index: CodeIndex, file_path: str) -> list[str]:
        """Find all files that import the given file."""
        return index.reverse_dependencies.get(file_path, [])

    def get_file_context(self, index: CodeIndex, file_path: str) -> dict:
        """Get full context for a file: symbols, deps, dependents."""
        return {
            "file_path": file_path,
            "symbols": index.file_symbols.get(file_path, []),
            "imports": index.dependencies.get(file_path, []),
            "imported_by": index.reverse_dependencies.get(file_path, []),
        }

    def trace_flow(
        self, 
        index: CodeIndex, 
        start_symbol: str, 
        max_depth: int = 5,
        direction: str = "callees"  # "callees" or "callers"
    ) -> list[list[str]]:
        """
        Trace call flow from a symbol.
        Returns list of call chains.
        """
        chains = []
        visited = set()

        def trace(current: str, chain: list[str], depth: int):
            if depth > max_depth:
                return
            if current in visited:
                return
            
            visited.add(current)
            new_chain = chain + [current]

            if direction == "callees":
                next_symbols = self.find_callees(index, current)
            else:
                next_symbols = self.find_callers(index, current)

            if not next_symbols:
                chains.append(new_chain)
                return

            for next_sym in next_symbols[:10]:  # Limit branching
                trace(next_sym, new_chain, depth + 1)

        trace(start_symbol, [], 0)
        return chains

    def get_entry_points(self, index: CodeIndex) -> list[Symbol]:
        """Find likely entry points (main functions, route handlers, CLI commands)."""
        entry_points = []
        
        entry_point_patterns = [
            "main", "__main__", "app", "server", "index",
            "handle", "handler", "route", "endpoint", "view",
            "cli", "command", "run", "start", "init",
        ]

        for name, symbols in index.symbol_table.items():
            name_lower = name.lower()
            for pattern in entry_point_patterns:
                if pattern in name_lower:
                    for sym in symbols:
                        if sym.type in ("function", "method"):
                            # Check if it's not called by anything (true entry point)
                            callers = self.find_callers(index, sym.qualified_name)
                            if not callers or sym.name in ("main", "__main__", "app"):
                                entry_points.append(sym)
                    break

        # Also add functions with decorators like @app.route, @router.get, etc.
        for symbols in index.file_symbols.values():
            for sym in symbols:
                if sym.body and sym.type in ("function", "method"):
                    body_lower = sym.body.lower() if sym.body else ""
                    if any(p in body_lower for p in ["@app.", "@router.", "@route", "@get", "@post", "@put", "@delete"]):
                        if sym not in entry_points:
                            entry_points.append(sym)

        return entry_points

    def get_top_level_symbols(self, index: CodeIndex, limit: int = 20) -> list[Symbol]:
        """Get the most important top-level symbols."""
        # Prioritize: classes first, then functions with many callers
        classes = []
        functions = []

        for symbols in index.symbol_table.values():
            for sym in symbols:
                if sym.type == "class" and not sym.parent:
                    # Count methods
                    method_count = len(sym.children)
                    classes.append((sym, method_count))
                elif sym.type == "function" and not sym.parent:
                    # Count callers
                    caller_count = len(self.find_callers(index, sym.qualified_name))
                    functions.append((sym, caller_count))

        # Sort by importance (method count for classes, caller count for functions)
        classes.sort(key=lambda x: x[1], reverse=True)
        functions.sort(key=lambda x: x[1], reverse=True)

        # Combine: take top classes, then top functions
        result = []
        for sym, _ in classes[:limit // 2]:
            result.append(sym)
        for sym, _ in functions[:limit // 2]:
            result.append(sym)

        return result[:limit]

    def search_symbols(
        self,
        index: CodeIndex,
        query: str,
        types: Optional[list[str]] = None,
        file_pattern: Optional[str] = None,
        limit: int = 20
    ) -> list[Symbol]:
        """Search symbols with multiple criteria."""
        results = []
        query_lower = query.lower()

        for name, symbols in index.symbol_table.items():
            if query_lower in name.lower():
                for sym in symbols:
                    # Filter by type
                    if types and sym.type not in types:
                        continue
                    
                    # Filter by file pattern
                    if file_pattern and file_pattern not in sym.file_path:
                        continue
                    
                    results.append(sym)
                    
                    if len(results) >= limit:
                        return results

        return results

    def get_symbol_with_context(
        self,
        index: CodeIndex,
        qualified_name: str
    ) -> Optional[dict]:
        """Get a symbol with its full context (callers, callees, deps)."""
        # Find the symbol
        symbol = None
        for symbols in index.symbol_table.values():
            for sym in symbols:
                if sym.qualified_name == qualified_name:
                    symbol = sym
                    break
            if symbol:
                break

        if not symbol:
            return None

        return {
            "symbol": symbol,
            "callers": self.find_callers(index, qualified_name),
            "callees": self.find_callees(index, qualified_name),
            "file_context": self.get_file_context(index, symbol.file_path),
        }
