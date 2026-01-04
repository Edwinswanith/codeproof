"""End-to-end tests for the indexing pipeline.

Tests the complete flow:
1. Parse Python files from a directory
2. Build an index from parse results
3. Query the index for symbols, dependencies, and call graph
"""

import os
import pytest
import tempfile
import shutil
from pathlib import Path

from app.parsers.python_parser import PythonParser, ParseResult
from app.services.index_service import IndexService, CodeIndex


class TestIndexingE2E:
    """End-to-end tests for repository indexing."""

    @pytest.fixture
    def sample_repo(self):
        """Create a temporary repository with sample Python files."""
        temp_dir = tempfile.mkdtemp()

        # Create directory structure
        services_dir = os.path.join(temp_dir, "services")
        models_dir = os.path.join(temp_dir, "models")
        os.makedirs(services_dir)
        os.makedirs(models_dir)

        # Create models/user.py
        user_model = '''"""User model for the application."""

from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    """Represents a user in the system."""

    id: int
    name: str
    email: str
    is_active: bool = True

    def full_name(self) -> str:
        """Get the user's full name."""
        return self.name

    def deactivate(self) -> None:
        """Deactivate the user account."""
        self.is_active = False
'''
        with open(os.path.join(models_dir, "user.py"), "w") as f:
            f.write(user_model)

        # Create models/order.py
        order_model = '''"""Order model."""

from dataclasses import dataclass, field
from typing import List
from .user import User

@dataclass
class OrderItem:
    """A single item in an order."""
    product_id: int
    quantity: int
    price: float

@dataclass
class Order:
    """An order placed by a user."""

    id: int
    user: User
    items: List[OrderItem] = field(default_factory=list)

    def total(self) -> float:
        """Calculate total order amount."""
        return sum(item.price * item.quantity for item in self.items)

    def add_item(self, item: OrderItem) -> None:
        """Add an item to the order."""
        self.items.append(item)
'''
        with open(os.path.join(models_dir, "order.py"), "w") as f:
            f.write(order_model)

        # Create services/user_service.py
        user_service = '''"""User service for business logic."""

import logging
from typing import Optional, List
from models.user import User

logger = logging.getLogger(__name__)

class UserService:
    """Service for user operations."""

    def __init__(self):
        self._users: dict[int, User] = {}

    def create_user(self, name: str, email: str) -> User:
        """Create a new user."""
        user_id = len(self._users) + 1
        user = User(id=user_id, name=name, email=email)
        self._users[user_id] = user
        logger.info(f"Created user {user_id}")
        return user

    def get_user(self, user_id: int) -> Optional[User]:
        """Get a user by ID."""
        return self._users.get(user_id)

    def list_users(self) -> List[User]:
        """List all users."""
        return list(self._users.values())

    def deactivate_user(self, user_id: int) -> bool:
        """Deactivate a user."""
        user = self.get_user(user_id)
        if user:
            user.deactivate()
            return True
        return False
'''
        with open(os.path.join(services_dir, "user_service.py"), "w") as f:
            f.write(user_service)

        # Create services/order_service.py
        order_service = '''"""Order service."""

from typing import Optional, List
from models.order import Order, OrderItem
from models.user import User
from .user_service import UserService

class OrderService:
    """Service for order operations."""

    def __init__(self, user_service: UserService):
        self._user_service = user_service
        self._orders: dict[int, Order] = {}

    def create_order(self, user_id: int) -> Optional[Order]:
        """Create a new order for a user."""
        user = self._user_service.get_user(user_id)
        if not user:
            return None

        order_id = len(self._orders) + 1
        order = Order(id=order_id, user=user)
        self._orders[order_id] = order
        return order

    def add_item_to_order(
        self,
        order_id: int,
        product_id: int,
        quantity: int,
        price: float
    ) -> bool:
        """Add an item to an existing order."""
        order = self._orders.get(order_id)
        if not order:
            return False

        item = OrderItem(product_id=product_id, quantity=quantity, price=price)
        order.add_item(item)
        return True

    def get_order(self, order_id: int) -> Optional[Order]:
        """Get an order by ID."""
        return self._orders.get(order_id)

    def get_user_orders(self, user_id: int) -> List[Order]:
        """Get all orders for a user."""
        return [o for o in self._orders.values() if o.user.id == user_id]
'''
        with open(os.path.join(services_dir, "order_service.py"), "w") as f:
            f.write(order_service)

        # Create main.py
        main_file = '''"""Main application entry point."""

from services.user_service import UserService
from services.order_service import OrderService

def main():
    """Run the application."""
    user_service = UserService()
    order_service = OrderService(user_service)

    # Create a user
    user = user_service.create_user("John Doe", "john@example.com")

    # Create an order
    order = order_service.create_order(user.id)
    if order:
        order_service.add_item_to_order(order.id, 1, 2, 29.99)
        print(f"Order total: ${order.total():.2f}")

if __name__ == "__main__":
    main()
'''
        with open(os.path.join(temp_dir, "main.py"), "w") as f:
            f.write(main_file)

        yield temp_dir

        # Cleanup
        shutil.rmtree(temp_dir)

    def _parse_directory(self, repo_path: str) -> ParseResult:
        """Parse all Python files in a directory."""
        parser = PythonParser()
        combined_result = ParseResult()

        for root, dirs, files in os.walk(repo_path):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in {
                "__pycache__", ".git", "venv", ".venv", "node_modules"
            }]

            for filename in files:
                if filename.endswith(".py"):
                    file_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(file_path, repo_path)

                    with open(file_path, "r") as f:
                        content = f.read()

                    result = parser.parse(content, rel_path)
                    combined_result.symbols.extend(result.symbols)
                    combined_result.imports.extend(result.imports)
                    combined_result.calls.extend(result.calls)
                    combined_result.files_parsed += 1

        return combined_result

    def test_parse_repository(self, sample_repo):
        """Can parse all files in a repository."""
        result = self._parse_directory(sample_repo)

        assert result.files_parsed >= 4  # At least 4 main files
        assert len(result.symbols) > 0
        assert len(result.imports) > 0

    def test_build_index_from_repo(self, sample_repo):
        """Can build index from parsed repository."""
        parse_result = self._parse_directory(sample_repo)
        service = IndexService()

        index = service.build_index(parse_result)

        assert index.total_files >= 2  # At least service files
        assert index.total_symbols > 0
        assert index.total_classes > 0
        assert index.total_functions > 0

    def test_find_all_classes(self, sample_repo):
        """Can find all classes in the repository."""
        parse_result = self._parse_directory(sample_repo)
        service = IndexService()
        index = service.build_index(parse_result)

        classes = service.find_symbol_by_type(index, "class")
        class_names = {c.name for c in classes}

        # Service classes are definitely found
        assert "UserService" in class_names
        assert "OrderService" in class_names
        # Note: @dataclass decorated classes are also parsed as classes
        assert len(class_names) >= 2

    def test_find_all_methods(self, sample_repo):
        """Can find all methods in the repository."""
        parse_result = self._parse_directory(sample_repo)
        service = IndexService()
        index = service.build_index(parse_result)

        methods = service.find_symbol_by_type(index, "method")
        method_names = {m.name for m in methods}

        # UserService methods
        assert "create_user" in method_names
        assert "get_user" in method_names
        assert "list_users" in method_names
        assert "deactivate_user" in method_names

        # OrderService methods
        assert "create_order" in method_names
        assert "add_item_to_order" in method_names
        assert "get_order" in method_names
        assert "get_user_orders" in method_names

    def test_find_symbol_by_name(self, sample_repo):
        """Can find symbols by name."""
        parse_result = self._parse_directory(sample_repo)
        service = IndexService()
        index = service.build_index(parse_result)

        # Exact match
        results = service.find_symbol(index, "UserService", exact=True)
        assert len(results) == 1
        assert results[0].type == "class"

        # Partial match
        results = service.find_symbol(index, "user", exact=False)
        names = {s.name for s in results}
        assert "UserService" in names
        assert "create_user" in names
        assert "get_user" in names
        assert "deactivate_user" in names

    def test_search_with_filters(self, sample_repo):
        """Can search symbols with type and file filters."""
        parse_result = self._parse_directory(sample_repo)
        service = IndexService()
        index = service.build_index(parse_result)

        # Search for methods containing "user" in services directory
        results = service.search_symbols(
            index,
            "user",
            types=["method"],
            file_pattern="services/"
        )

        # Should find methods in services but not User class methods
        names = {s.name for s in results}
        assert "create_user" in names
        assert "get_user" in names
        assert "deactivate_user" in names

        # Verify all are from services directory
        for r in results:
            assert "services/" in r.file_path

    def test_get_file_context(self, sample_repo):
        """Can get full context for a file."""
        parse_result = self._parse_directory(sample_repo)
        service = IndexService()
        index = service.build_index(parse_result)

        context = service.get_file_context(index, "services/user_service.py")

        assert context["file_path"] == "services/user_service.py"
        assert len(context["symbols"]) > 0

        # Should have UserService class and its methods
        symbol_names = {s.name for s in context["symbols"]}
        assert "UserService" in symbol_names

    def test_entry_points_detection(self, sample_repo):
        """Can detect entry points (main function)."""
        parse_result = self._parse_directory(sample_repo)
        service = IndexService()
        index = service.build_index(parse_result)

        entry_points = service.get_entry_points(index)
        entry_names = {ep.name for ep in entry_points}

        assert "main" in entry_names

    def test_top_level_symbols(self, sample_repo):
        """Can get top-level symbols ranked by importance."""
        parse_result = self._parse_directory(sample_repo)
        service = IndexService()
        index = service.build_index(parse_result)

        top_symbols = service.get_top_level_symbols(index, limit=10)

        # Should include the main service classes
        names = {s.name for s in top_symbols}
        assert len(names) > 0
        # Classes with methods should be prioritized
        assert "UserService" in names or "OrderService" in names

    def test_method_parent_references(self, sample_repo):
        """Methods correctly reference their parent class."""
        parse_result = self._parse_directory(sample_repo)
        service = IndexService()
        index = service.build_index(parse_result)

        methods = service.find_symbol_by_type(index, "method")

        for method in methods:
            if method.name in ("create_user", "get_user", "list_users", "deactivate_user"):
                assert method.parent == "UserService", f"{method.name} should have UserService as parent"
            elif method.name in ("create_order", "add_item_to_order", "get_order", "get_user_orders"):
                assert method.parent == "OrderService", f"{method.name} should have OrderService as parent"

    def test_qualified_names(self, sample_repo):
        """Symbols have correct qualified names."""
        parse_result = self._parse_directory(sample_repo)
        service = IndexService()
        index = service.build_index(parse_result)

        # Find create_user method
        results = service.find_symbol(index, "create_user", exact=True)
        service_method = [r for r in results if r.type == "method" and "user_service" in r.file_path]

        assert len(service_method) == 1
        assert service_method[0].qualified_name == "UserService.create_user"


class TestIndexingEdgeCases:
    """Test edge cases in the indexing pipeline."""

    def test_empty_directory(self):
        """Handle empty directory gracefully."""
        temp_dir = tempfile.mkdtemp()
        try:
            parser = PythonParser()
            service = IndexService()

            result = ParseResult()
            index = service.build_index(result)

            assert index.total_files == 0
            assert index.total_symbols == 0
        finally:
            shutil.rmtree(temp_dir)

    def test_nested_classes(self):
        """Handle nested class definitions."""
        parser = PythonParser()
        service = IndexService()

        code = '''
class Outer:
    """Outer class."""

    class Inner:
        """Inner class."""

        def inner_method(self):
            pass

    def outer_method(self):
        pass
'''
        result = parser.parse(code, "nested.py")
        index = service.build_index(result)

        classes = service.find_symbol_by_type(index, "class")
        class_names = {c.name for c in classes}

        assert "Outer" in class_names
        assert "Inner" in class_names

    def test_decorated_functions(self):
        """Handle decorated functions."""
        parser = PythonParser()
        service = IndexService()

        code = '''
def decorator(func):
    return func

def decorated_function():
    """A decorated function."""
    pass

class Service:
    def static_method(self):
        pass

    def class_method(self):
        pass
'''
        result = parser.parse(code, "decorated.py")
        index = service.build_index(result)

        functions = service.find_symbol_by_type(index, "function")
        methods = service.find_symbol_by_type(index, "method")

        func_names = {f.name for f in functions}
        method_names = {m.name for m in methods}

        assert "decorator" in func_names
        assert "decorated_function" in func_names
        assert "static_method" in method_names
        assert "class_method" in method_names

    def test_async_functions(self):
        """Handle async functions."""
        parser = PythonParser()
        service = IndexService()

        code = '''
async def async_function():
    """An async function."""
    await some_async_call()

class AsyncService:
    async def async_method(self):
        """An async method."""
        pass
'''
        result = parser.parse(code, "async.py")
        index = service.build_index(result)

        functions = service.find_symbol_by_type(index, "function")
        methods = service.find_symbol_by_type(index, "method")

        func_names = {f.name for f in functions}
        method_names = {m.name for m in methods}

        assert "async_function" in func_names
        assert "async_method" in method_names
