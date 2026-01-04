"""Pytest configuration and fixtures."""

import pytest
import asyncio
from typing import Generator

# Sample Python code for testing
SAMPLE_PYTHON_SIMPLE = '''
def hello_world():
    """A simple greeting function."""
    return "Hello, World!"
'''

SAMPLE_PYTHON_CLASS = '''
class Calculator:
    """A simple calculator class."""

    def __init__(self, initial_value: int = 0):
        """Initialize with a starting value."""
        self.value = initial_value

    def add(self, x: int) -> int:
        """Add x to the current value."""
        self.value += x
        return self.value

    def subtract(self, x: int) -> int:
        """Subtract x from the current value."""
        self.value -= x
        return self.value
'''

SAMPLE_PYTHON_IMPORTS = '''
import os
import sys
from typing import Optional, List
from collections import defaultdict
from dataclasses import dataclass, field

def process_data(items: List[str]) -> Optional[dict]:
    """Process a list of items."""
    if not items:
        return None
    return {"count": len(items), "items": items}
'''

SAMPLE_PYTHON_COMPLEX = '''
"""Module docstring for complex example."""

import logging
from typing import Optional, List, Dict
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class BaseProcessor(ABC):
    """Abstract base class for processors."""

    @abstractmethod
    def process(self, data: str) -> str:
        """Process the input data."""
        pass

class TextProcessor(BaseProcessor):
    """Concrete text processor implementation."""

    def __init__(self, prefix: str = ""):
        self.prefix = prefix
        self._cache: Dict[str, str] = {}

    def process(self, data: str) -> str:
        """Process text by adding prefix."""
        if data in self._cache:
            return self._cache[data]
        result = f"{self.prefix}{data}"
        self._cache[data] = result
        return result

    def clear_cache(self) -> None:
        """Clear the internal cache."""
        self._cache.clear()

def create_processor(prefix: str = "") -> TextProcessor:
    """Factory function to create a processor."""
    return TextProcessor(prefix)

async def async_process(data: str) -> str:
    """Async processing function."""
    import asyncio
    await asyncio.sleep(0.1)
    return data.upper()

CONSTANT_VALUE = 42
'''

SAMPLE_PYTHON_NESTED = '''
class Outer:
    """Outer class with nested class."""

    class Inner:
        """Nested inner class."""

        def inner_method(self):
            """Method in inner class."""
            return "inner"

    def outer_method(self):
        """Method in outer class."""
        return "outer"

def outer_function():
    """Function with nested function."""

    def inner_function():
        """Nested function."""
        return "nested"

    return inner_function()
'''


@pytest.fixture
def sample_python_simple():
    """Simple function sample."""
    return SAMPLE_PYTHON_SIMPLE


@pytest.fixture
def sample_python_class():
    """Class with methods sample."""
    return SAMPLE_PYTHON_CLASS


@pytest.fixture
def sample_python_imports():
    """Imports sample."""
    return SAMPLE_PYTHON_IMPORTS


@pytest.fixture
def sample_python_complex():
    """Complex module sample."""
    return SAMPLE_PYTHON_COMPLEX


@pytest.fixture
def sample_python_nested():
    """Nested structures sample."""
    return SAMPLE_PYTHON_NESTED


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
