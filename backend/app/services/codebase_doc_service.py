"""AI-Ready Codebase Documentation Generator.

Generates structured documentation optimized for AI code assistants
(Claude Code, Cursor, Copilot) to understand and navigate the codebase.

Outputs:
- CODEBASE.md: High-level overview, architecture, key patterns
- ARCHITECTURE.md: System design, data flow, component relationships
- SYMBOL_MAP.md: Organized reference of all symbols
- .ai/context.json: Machine-readable context for AI tools
"""

import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
from datetime import datetime

from app.services.index_service import CodeIndex
from app.services.parser_service import ParseResult, Symbol

logger = logging.getLogger(__name__)


@dataclass
class CodebaseContext:
    """Machine-readable context for AI tools."""
    repo_url: str
    analyzed_at: str
    framework: str
    language_breakdown: dict[str, int]  # language -> file count
    entry_points: list[dict]
    key_patterns: list[str]
    important_files: list[str]
    directory_structure: dict
    symbol_summary: dict[str, int]  # type -> count


class CodebaseDocService:
    """Generates AI-optimized documentation for codebases."""

    def __init__(self):
        """Initialize documentation generator."""
        pass

    def generate_all_docs(
        self,
        repo_path: str,
        repo_url: str,
        parse_result: ParseResult,
        index: CodeIndex,
        framework: str = "unknown",
        output_dir: Optional[str] = None,
    ) -> dict[str, str]:
        """
        Generate all documentation files.

        Returns dict mapping filename to content.
        """
        docs = {}

        # Generate each document
        docs["CODEBASE.md"] = self.generate_codebase_overview(
            repo_url, parse_result, index, framework
        )

        docs["ARCHITECTURE.md"] = self.generate_architecture_doc(
            parse_result, index, framework
        )

        docs["SYMBOL_MAP.md"] = self.generate_symbol_map(
            parse_result, index
        )

        docs[".ai/context.json"] = self.generate_ai_context(
            repo_url, parse_result, index, framework
        )

        # Write files if output_dir provided
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            for filename, content in docs.items():
                file_path = output_path / filename
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)
                logger.info(f"Generated {file_path}")

        return docs

    def generate_codebase_overview(
        self,
        repo_url: str,
        parse_result: ParseResult,
        index: CodeIndex,
        framework: str,
    ) -> str:
        """Generate CODEBASE.md - high-level overview."""

        # Analyze language breakdown
        lang_breakdown = self._get_language_breakdown(parse_result)
        primary_lang = max(lang_breakdown.items(), key=lambda x: x[1])[0] if lang_breakdown else "Unknown"

        # Get entry points
        entry_points = index.get_entry_points(limit=15)

        # Get top-level symbols
        top_symbols = index.get_top_level_symbols(limit=20)

        # Identify key directories
        key_dirs = self._identify_key_directories(parse_result)

        # Detect patterns
        patterns = self._detect_patterns(parse_result, index)

        doc = f"""# Codebase Overview

> Auto-generated documentation for AI code assistants

**Repository:** {repo_url}
**Framework:** {framework}
**Primary Language:** {primary_lang}
**Generated:** {datetime.now().isoformat()}

---

## Quick Start for AI Assistants

When working with this codebase:

1. **Entry Points** - Start here to understand the application flow
2. **Key Directories** - Organized by functionality
3. **Core Symbols** - Most important classes and functions
4. **Patterns** - Coding conventions used

---

## Language Breakdown

| Language | Files |
|----------|-------|
{self._format_table(lang_breakdown)}

---

## Entry Points

These are the main entry points into the application:

{self._format_entry_points(entry_points)}

---

## Key Directories

{self._format_key_dirs(key_dirs)}

---

## Core Symbols

The most important classes and functions:

### Classes

{self._format_symbols([s for s in top_symbols if s.type == 'class'][:10])}

### Functions

{self._format_symbols([s for s in top_symbols if s.type in ('function', 'method')][:10])}

---

## Detected Patterns

{self._format_patterns(patterns)}

---

## File Statistics

- **Total Files Parsed:** {parse_result.files_parsed}
- **Total Symbols:** {len(parse_result.symbols)}
- **Classes:** {sum(1 for s in parse_result.symbols if s.type == 'class')}
- **Functions:** {sum(1 for s in parse_result.symbols if s.type in ('function', 'method'))}
- **Parse Errors:** {len(parse_result.errors)}

---

## How to Navigate

1. Use `ARCHITECTURE.md` for system design and data flow
2. Use `SYMBOL_MAP.md` for finding specific symbols
3. Use `.ai/context.json` for programmatic access

"""
        return doc

    def generate_architecture_doc(
        self,
        parse_result: ParseResult,
        index: CodeIndex,
        framework: str,
    ) -> str:
        """Generate ARCHITECTURE.md - system design documentation."""

        # Build dependency graph visualization
        dep_graph = self._build_dependency_summary(index)

        # Identify layers/modules
        layers = self._identify_layers(parse_result)

        # Build call graph summary
        call_summary = self._build_call_graph_summary(index)

        doc = f"""# Architecture Overview

> System design and component relationships

**Framework:** {framework}

---

## System Layers

{self._format_layers(layers)}

---

## Module Dependencies

```
{dep_graph}
```

---

## Key Data Flows

{call_summary}

---

## Component Relationships

### Import Graph

Files organized by their import relationships:

{self._format_import_graph(index)}

---

## Design Patterns Identified

{self._identify_design_patterns(parse_result, index)}

"""
        return doc

    def generate_symbol_map(
        self,
        parse_result: ParseResult,
        index: CodeIndex,
    ) -> str:
        """Generate SYMBOL_MAP.md - organized symbol reference."""

        # Group symbols by file
        symbols_by_file = {}
        for symbol in parse_result.symbols:
            if symbol.file_path not in symbols_by_file:
                symbols_by_file[symbol.file_path] = []
            symbols_by_file[symbol.file_path].append(symbol)

        # Group by type
        classes = [s for s in parse_result.symbols if s.type == 'class']
        functions = [s for s in parse_result.symbols if s.type == 'function']
        methods = [s for s in parse_result.symbols if s.type == 'method']

        doc = f"""# Symbol Map

> Complete reference of all code symbols

**Total Symbols:** {len(parse_result.symbols)}

---

## Quick Reference

| Type | Count |
|------|-------|
| Classes | {len(classes)} |
| Functions | {len(functions)} |
| Methods | {len(methods)} |

---

## Classes

{self._format_class_index(classes)}

---

## Top-Level Functions

{self._format_function_index(functions)}

---

## Symbols by File

{self._format_symbols_by_file(symbols_by_file)}

---

## Search Tips

To find a symbol:
1. Search for the symbol name in this file
2. Look up the file path and line number
3. Use your IDE to navigate

"""
        return doc

    def generate_ai_context(
        self,
        repo_url: str,
        parse_result: ParseResult,
        index: CodeIndex,
        framework: str,
    ) -> str:
        """Generate .ai/context.json - machine-readable context."""

        lang_breakdown = self._get_language_breakdown(parse_result)
        entry_points = index.get_entry_points(limit=20)

        context = CodebaseContext(
            repo_url=repo_url,
            analyzed_at=datetime.now().isoformat(),
            framework=framework,
            language_breakdown=lang_breakdown,
            entry_points=[
                {
                    "name": ep.name,
                    "type": ep.type,
                    "file": ep.file_path,
                    "line": ep.line_start,
                    "signature": ep.signature or "",
                }
                for ep in entry_points
            ],
            key_patterns=self._detect_patterns(parse_result, index),
            important_files=self._get_important_files(parse_result),
            directory_structure=self._get_directory_structure(parse_result),
            symbol_summary={
                "classes": sum(1 for s in parse_result.symbols if s.type == 'class'),
                "functions": sum(1 for s in parse_result.symbols if s.type == 'function'),
                "methods": sum(1 for s in parse_result.symbols if s.type == 'method'),
                "total": len(parse_result.symbols),
            }
        )

        return json.dumps(asdict(context), indent=2)

    # Helper methods

    def _get_language_breakdown(self, parse_result: ParseResult) -> dict[str, int]:
        """Count files by language/extension."""
        breakdown = {}
        for symbol in parse_result.symbols:
            ext = Path(symbol.file_path).suffix.lower()
            lang = self._ext_to_language(ext)
            breakdown[lang] = breakdown.get(lang, 0) + 1

        # Normalize by unique files
        file_langs = {}
        for symbol in parse_result.symbols:
            ext = Path(symbol.file_path).suffix.lower()
            lang = self._ext_to_language(ext)
            file_langs[symbol.file_path] = lang

        return {lang: sum(1 for l in file_langs.values() if l == lang)
                for lang in set(file_langs.values())}

    def _ext_to_language(self, ext: str) -> str:
        """Map file extension to language name."""
        mapping = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.tsx': 'TypeScript (React)',
            '.jsx': 'JavaScript (React)',
            '.php': 'PHP',
            '.rb': 'Ruby',
            '.java': 'Java',
            '.go': 'Go',
            '.rs': 'Rust',
            '.cs': 'C#',
            '.vue': 'Vue',
            '.svelte': 'Svelte',
        }
        return mapping.get(ext, ext or 'Unknown')

    def _identify_key_directories(self, parse_result: ParseResult) -> dict[str, str]:
        """Identify key directories and their purposes."""
        dirs = {}
        for symbol in parse_result.symbols:
            parts = Path(symbol.file_path).parts
            if len(parts) >= 2:
                top_dir = parts[0]
                if top_dir not in dirs:
                    dirs[top_dir] = self._guess_dir_purpose(top_dir)
        return dirs

    def _guess_dir_purpose(self, dir_name: str) -> str:
        """Guess the purpose of a directory from its name."""
        purposes = {
            'src': 'Source code',
            'app': 'Application code',
            'lib': 'Library/utilities',
            'api': 'API routes/endpoints',
            'routes': 'URL routes',
            'controllers': 'Request controllers',
            'models': 'Data models',
            'views': 'View templates',
            'components': 'UI components',
            'services': 'Business logic services',
            'utils': 'Utility functions',
            'helpers': 'Helper functions',
            'tests': 'Test files',
            'config': 'Configuration',
            'database': 'Database related',
            'migrations': 'Database migrations',
            'middleware': 'Middleware',
            'static': 'Static assets',
            'public': 'Public files',
            'assets': 'Asset files',
        }
        return purposes.get(dir_name.lower(), 'Project files')

    def _detect_patterns(self, parse_result: ParseResult, index: CodeIndex) -> list[str]:
        """Detect coding patterns used in the codebase."""
        patterns = []

        # Check for common patterns
        symbol_names = {s.name.lower() for s in parse_result.symbols}

        if any('controller' in n for n in symbol_names):
            patterns.append("MVC Pattern (Controllers)")
        if any('service' in n for n in symbol_names):
            patterns.append("Service Layer Pattern")
        if any('repository' in n for n in symbol_names):
            patterns.append("Repository Pattern")
        if any('factory' in n for n in symbol_names):
            patterns.append("Factory Pattern")
        if any('singleton' in n for n in symbol_names):
            patterns.append("Singleton Pattern")
        if any('handler' in n for n in symbol_names):
            patterns.append("Handler/Command Pattern")
        if any('middleware' in n for n in symbol_names):
            patterns.append("Middleware Pattern")
        if any('decorator' in n or 'wrapper' in n for n in symbol_names):
            patterns.append("Decorator Pattern")

        # Check imports for framework patterns
        for imp in parse_result.imports:
            mod = imp.module.lower() if imp.module else ""
            if 'fastapi' in mod or 'flask' in mod or 'django' in mod:
                patterns.append("Web Framework (Python)")
            if 'react' in mod or 'vue' in mod or 'angular' in mod:
                patterns.append("Frontend Framework")
            if 'sqlalchemy' in mod or 'sequelize' in mod:
                patterns.append("ORM Pattern")

        return list(set(patterns))[:10]

    def _format_table(self, data: dict) -> str:
        """Format dict as markdown table rows."""
        return '\n'.join(f"| {k} | {v} |" for k, v in sorted(data.items(), key=lambda x: -x[1]))

    def _format_entry_points(self, entry_points: list[Symbol]) -> str:
        """Format entry points as markdown list."""
        if not entry_points:
            return "_No entry points detected_"

        lines = []
        for ep in entry_points:
            sig = f"`{ep.signature}`" if ep.signature else ""
            lines.append(f"- **{ep.name}** ({ep.type}) - `{ep.file_path}:{ep.line_start}` {sig}")
        return '\n'.join(lines)

    def _format_key_dirs(self, dirs: dict[str, str]) -> str:
        """Format key directories."""
        if not dirs:
            return "_No directories identified_"

        lines = []
        for dir_name, purpose in sorted(dirs.items()):
            lines.append(f"- **`{dir_name}/`** - {purpose}")
        return '\n'.join(lines)

    def _format_symbols(self, symbols: list[Symbol]) -> str:
        """Format symbol list."""
        if not symbols:
            return "_None_"

        lines = []
        for s in symbols:
            sig = s.signature or s.name
            lines.append(f"- `{sig}` - `{s.file_path}:{s.line_start}`")
        return '\n'.join(lines)

    def _format_patterns(self, patterns: list[str]) -> str:
        """Format detected patterns."""
        if not patterns:
            return "_No specific patterns detected_"
        return '\n'.join(f"- {p}" for p in patterns)

    def _identify_layers(self, parse_result: ParseResult) -> dict[str, list[str]]:
        """Identify architectural layers."""
        layers = {
            "Presentation": [],
            "Business Logic": [],
            "Data Access": [],
            "Infrastructure": [],
        }

        for symbol in parse_result.symbols:
            path = symbol.file_path.lower()
            name = symbol.name.lower()

            if any(x in path for x in ['route', 'controller', 'view', 'component', 'page']):
                layers["Presentation"].append(f"{symbol.name} ({symbol.file_path})")
            elif any(x in path for x in ['service', 'usecase', 'business']):
                layers["Business Logic"].append(f"{symbol.name} ({symbol.file_path})")
            elif any(x in path for x in ['model', 'repository', 'database', 'dao']):
                layers["Data Access"].append(f"{symbol.name} ({symbol.file_path})")
            elif any(x in path for x in ['config', 'middleware', 'util', 'helper']):
                layers["Infrastructure"].append(f"{symbol.name} ({symbol.file_path})")

        return {k: v[:5] for k, v in layers.items()}  # Limit each layer

    def _format_layers(self, layers: dict[str, list[str]]) -> str:
        """Format layer information."""
        lines = []
        for layer, items in layers.items():
            lines.append(f"### {layer}")
            if items:
                for item in items:
                    lines.append(f"- {item}")
            else:
                lines.append("_No components identified_")
            lines.append("")
        return '\n'.join(lines)

    def _build_dependency_summary(self, index: CodeIndex) -> str:
        """Build ASCII dependency graph."""
        if not index.dependencies:
            return "No dependencies mapped"

        # Get top files with most dependencies
        top_files = sorted(
            index.dependencies.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:10]

        lines = []
        for file, deps in top_files:
            short_file = Path(file).name
            lines.append(f"{short_file}")
            for dep in list(deps)[:3]:
                short_dep = Path(dep).name
                lines.append(f"  └── {short_dep}")

        return '\n'.join(lines) if lines else "No dependencies mapped"

    def _build_call_graph_summary(self, index: CodeIndex) -> str:
        """Build call graph summary."""
        if not index.call_graph:
            return "_No call graph data_"

        # Find functions with most callers (entry points)
        caller_counts = {}
        for caller, callees in index.call_graph.items():
            for callee in callees:
                caller_counts[callee] = caller_counts.get(callee, 0) + 1

        top_called = sorted(caller_counts.items(), key=lambda x: -x[1])[:10]

        if not top_called:
            return "_No call relationships detected_"

        lines = ["Most frequently called functions:\n"]
        for func, count in top_called:
            lines.append(f"- `{func}` (called {count} times)")

        return '\n'.join(lines)

    def _format_import_graph(self, index: CodeIndex) -> str:
        """Format import relationships."""
        if not index.dependencies:
            return "_No import data_"

        lines = []
        for file, deps in list(index.dependencies.items())[:10]:
            if deps:
                dep_list = ', '.join(Path(d).name for d in list(deps)[:3])
                lines.append(f"- `{Path(file).name}` imports: {dep_list}")

        return '\n'.join(lines) if lines else "_No imports_"

    def _identify_design_patterns(self, parse_result: ParseResult, index: CodeIndex) -> str:
        """Identify and document design patterns."""
        patterns = []

        # Look for specific patterns
        for symbol in parse_result.symbols:
            name = symbol.name.lower()
            if name.endswith('factory'):
                patterns.append(f"**Factory Pattern**: `{symbol.name}` at `{symbol.file_path}:{symbol.line_start}`")
            elif name.endswith('builder'):
                patterns.append(f"**Builder Pattern**: `{symbol.name}` at `{symbol.file_path}:{symbol.line_start}`")
            elif name.endswith('observer') or name.endswith('listener'):
                patterns.append(f"**Observer Pattern**: `{symbol.name}` at `{symbol.file_path}:{symbol.line_start}`")
            elif name.endswith('strategy'):
                patterns.append(f"**Strategy Pattern**: `{symbol.name}` at `{symbol.file_path}:{symbol.line_start}`")

        if not patterns:
            return "_No explicit design patterns identified from symbol names_"

        return '\n'.join(patterns[:10])

    def _format_class_index(self, classes: list[Symbol]) -> str:
        """Format class index."""
        if not classes:
            return "_No classes found_"

        lines = []
        for cls in sorted(classes, key=lambda x: x.name)[:30]:
            methods = [c.name for c in cls.children] if cls.children else []
            method_str = f" - methods: {', '.join(methods[:3])}" if methods else ""
            lines.append(f"- **{cls.name}** `{cls.file_path}:{cls.line_start}`{method_str}")

        return '\n'.join(lines)

    def _format_function_index(self, functions: list[Symbol]) -> str:
        """Format function index."""
        if not functions:
            return "_No top-level functions found_"

        lines = []
        for func in sorted(functions, key=lambda x: x.name)[:30]:
            sig = func.signature or func.name
            lines.append(f"- `{sig}` - `{func.file_path}:{func.line_start}`")

        return '\n'.join(lines)

    def _format_symbols_by_file(self, symbols_by_file: dict[str, list[Symbol]]) -> str:
        """Format symbols grouped by file."""
        lines = []

        for file_path in sorted(symbols_by_file.keys())[:20]:
            symbols = symbols_by_file[file_path]
            lines.append(f"\n### `{file_path}`\n")
            for s in symbols[:10]:
                lines.append(f"- {s.type}: **{s.name}** (L{s.line_start})")

        return '\n'.join(lines)

    def _get_important_files(self, parse_result: ParseResult) -> list[str]:
        """Identify important files."""
        file_symbol_count = {}
        for s in parse_result.symbols:
            file_symbol_count[s.file_path] = file_symbol_count.get(s.file_path, 0) + 1

        # Sort by symbol count
        sorted_files = sorted(file_symbol_count.items(), key=lambda x: -x[1])
        return [f for f, _ in sorted_files[:20]]

    def _get_directory_structure(self, parse_result: ParseResult) -> dict:
        """Build directory structure."""
        structure = {}
        for symbol in parse_result.symbols:
            parts = Path(symbol.file_path).parts
            current = structure
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            # Add file
            filename = parts[-1] if parts else symbol.file_path
            if filename not in current:
                current[filename] = []
            current[filename].append(symbol.name)

        return structure
