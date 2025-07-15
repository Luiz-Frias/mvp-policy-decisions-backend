#!/usr/bin/env python3
"""Static validation of WebSocket implementation.

This script performs static code analysis to verify WebSocket implementation
without requiring runtime initialization.
"""

import ast
import sys
from pathlib import Path


class WebSocketStaticValidator:
    """Performs static validation of WebSocket implementation."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.websocket_dir = self.project_root / "src/policy_core/websocket"
        self.results = {
            "passed": [],
            "failed": [],
            "warnings": [],
        }

    def log_pass(self, test: str, detail: str = "") -> None:
        """Log a passing test."""
        msg = f"✅ {test}"
        if detail:
            msg += f" - {detail}"
        print(msg)
        self.results["passed"].append(test)

    def log_fail(self, test: str, error: str) -> None:
        """Log a failing test."""
        msg = f"❌ {test} - {error}"
        print(msg)
        self.results["failed"].append((test, error))

    def log_warning(self, test: str, warning: str) -> None:
        """Log a warning."""
        msg = f"⚠️  {test} - {warning}"
        print(msg)
        self.results["warnings"].append((test, warning))

    def analyze_file(self, file_path: Path) -> ast.AST | None:
        """Parse a Python file into AST."""
        try:
            with open(file_path) as f:
                return ast.parse(f.read())
        except Exception as e:
            self.log_fail(f"Parse {file_path.name}", str(e))
            return None

    def find_classes(self, tree: ast.AST) -> list[ast.ClassDef]:
        """Find all class definitions in AST."""
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node)
        return classes

    def find_methods(self, class_def: ast.ClassDef) -> list[str]:
        """Find all method names in a class."""
        methods = []
        for node in class_def.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(node.name)
        return methods

    def find_attributes(self, class_def: ast.ClassDef) -> set[str]:
        """Find attributes assigned in __init__ method."""
        attributes = set()
        for node in class_def.body:
            if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                for stmt in ast.walk(node):
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Attribute) and isinstance(
                                target.value, ast.Name
                            ):
                                if target.value.id == "self":
                                    attributes.add(target.attr)
        return attributes

    def validate_manager(self) -> None:
        """Validate WebSocket connection manager."""
        print("\n🔍 Validating WebSocket Manager...")

        manager_file = self.websocket_dir / "manager.py"
        if not manager_file.exists():
            self.log_fail("Manager file", "Not found")
            return

        tree = self.analyze_file(manager_file)
        if not tree:
            return

        # Find ConnectionManager class
        classes = self.find_classes(tree)
        manager_class = None
        for cls in classes:
            if cls.name == "ConnectionManager":
                manager_class = cls
                break

        if not manager_class:
            self.log_fail("ConnectionManager class", "Not found")
            return

        self.log_pass("ConnectionManager class found")

        # Check required attributes
        attributes = self.find_attributes(manager_class)
        required_attrs = [
            "_connections",
            "_room_subscriptions",
            "_connection_metadata",
            "_monitor",
            "_max_connections_allowed",
        ]

        for attr in required_attrs:
            if attr in attributes:
                self.log_pass(f"Manager attribute: {attr}")
            else:
                self.log_fail(f"Manager attribute: {attr}", "Not found in __init__")

        # Check if max_connections is 10000
        for node in ast.walk(manager_class):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and target.attr == "_max_connections_allowed"
                    ):
                        if (
                            isinstance(node.value, ast.Constant)
                            and node.value.value >= 10000
                        ):
                            self.log_pass(
                                "Max connections",
                                f"Set to {node.value.value:,}",
                            )

        # Check required methods
        methods = self.find_methods(manager_class)
        required_methods = [
            "connect",
            "disconnect",
            "subscribe_to_room",
            "unsubscribe_from_room",
            "send_personal_message",
            "send_to_room",
            "broadcast",
        ]

        for method in required_methods:
            if method in methods:
                self.log_pass(f"Manager method: {method}")
            else:
                self.log_fail(f"Manager method: {method}", "Not found")

    def validate_handlers(self) -> None:
        """Validate all WebSocket handlers."""
        print("\n🔍 Validating WebSocket Handlers...")

        handlers_dir = self.websocket_dir / "handlers"
        if not handlers_dir.exists():
            self.log_fail("Handlers directory", "Not found")
            return

        handler_files = {
            "quotes.py": (
                "QuoteWebSocketHandler",
                [
                    "handle_quote_subscribe",
                    "handle_quote_unsubscribe",
                    "broadcast_quote_update",
                    "handle_collaborative_edit",
                ],
            ),
            "analytics.py": (
                "AnalyticsWebSocketHandler",
                [
                    "handle_analytics_subscribe",
                    "broadcast_dashboard_update",
                    "handle_conversion_funnel_request",
                ],
            ),
            "notifications.py": (
                "NotificationHandler",
                [
                    "send_notification",
                    "handle_notification_acknowledge",
                    "broadcast_system_alert",
                ],
            ),
            "admin_dashboard.py": (
                "AdminDashboardHandler",
                [
                    "handle_admin_connect",
                    "start_system_monitoring",
                    "broadcast_system_metrics",
                ],
            ),
        }

        for filename, (class_name, required_methods) in handler_files.items():
            file_path = handlers_dir / filename
            if not file_path.exists():
                self.log_fail(f"Handler file: {filename}", "Not found")
                continue

            tree = self.analyze_file(file_path)
            if not tree:
                continue

            # Find handler class
            classes = self.find_classes(tree)
            handler_class = None
            for cls in classes:
                if cls.name == class_name:
                    handler_class = cls
                    break

            if not handler_class:
                self.log_fail(f"Handler class: {class_name}", "Not found")
                continue

            self.log_pass(f"Handler class: {class_name}")

            # Check methods
            methods = self.find_methods(handler_class)
            for method in required_methods:
                if method in methods:
                    self.log_pass(f"{class_name}.{method}")
                else:
                    self.log_fail(f"{class_name}.{method}", "Not found")

    def validate_monitoring(self) -> None:
        """Validate monitoring implementation."""
        print("\n🔍 Validating Performance Monitoring...")

        monitoring_file = self.websocket_dir / "monitoring.py"
        if not monitoring_file.exists():
            self.log_fail("Monitoring file", "Not found")
            return

        tree = self.analyze_file(monitoring_file)
        if not tree:
            return

        # Find WebSocketMonitor class
        classes = self.find_classes(tree)
        monitor_class = None
        for cls in classes:
            if cls.name == "WebSocketMonitor":
                monitor_class = cls
                break

        if not monitor_class:
            self.log_fail("WebSocketMonitor class", "Not found")
            return

        self.log_pass("WebSocketMonitor class found")

        # Check monitoring methods
        methods = self.find_methods(monitor_class)
        required_methods = [
            "record_connection_established",
            "record_connection_closed",
            "record_message_sent",
            "record_message_received",
            "record_error",
            "get_system_metrics",
            "get_performance_alerts",
        ]

        for method in required_methods:
            if method in methods:
                self.log_pass(f"Monitor method: {method}")
            else:
                self.log_fail(f"Monitor method: {method}", "Not found")

    def validate_integration(self) -> None:
        """Validate service integrations."""
        print("\n🔍 Validating Service Integration...")

        # Check quote service integration
        quote_service_file = (
            self.project_root / "src/policy_core/services/quote_service.py"
        )
        if quote_service_file.exists():
            tree = self.analyze_file(quote_service_file)
            if tree:
                # Check for WebSocket manager in __init__
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                        # Check parameters
                        for arg in node.args.args:
                            if arg.arg == "websocket_manager":
                                self.log_pass(
                                    "Quote service WebSocket parameter",
                                    "Found in __init__",
                                )
                                break

                # Check for _send_realtime_update method
                for node in ast.walk(tree):
                    if (
                        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and node.name == "_send_realtime_update"
                    ):
                        self.log_pass(
                            "Quote service real-time update",
                            "_send_realtime_update method found",
                        )

        # Check dependencies.py for WebSocket injection
        deps_file = self.project_root / "src/policy_core/api/dependencies.py"
        if deps_file.exists():
            with open(deps_file) as f:
                content = f.read()
                if "get_manager()" in content and "websocket_manager" in content:
                    self.log_pass(
                        "Dependencies WebSocket injection",
                        "WebSocket manager injection found",
                    )

    def validate_database_schema(self) -> None:
        """Validate database schema for WebSocket tables."""
        print("\n🔍 Validating Database Schema...")

        migrations_dir = self.project_root / "alembic/versions"
        if not migrations_dir.exists():
            self.log_fail("Migrations directory", "Not found")
            return

        required_tables = [
            "websocket_connections",
            "websocket_performance_logs",
            "websocket_connection_events",
            "websocket_connection_stats",
            "websocket_errors",
            "websocket_system_metrics",
            "performance_alerts",
            "analytics_events",
            "notification_queue",
            "realtime_metrics",
        ]

        found_tables = set()

        for migration_file in migrations_dir.glob("*.py"):
            with open(migration_file) as f:
                content = f.read()
                for table in required_tables:
                    if f'"{table}"' in content or f"'{table}'" in content:
                        found_tables.add(table)

        for table in required_tables:
            if table in found_tables:
                self.log_pass(f"Database table: {table}")
            else:
                self.log_fail(f"Database table: {table}", "Not found in migrations")

    def validate_no_silent_fallbacks(self) -> None:
        """Validate no silent fallbacks principle."""
        print("\n🔍 Validating No Silent Fallbacks...")

        # Check for Result type usage in manager
        manager_file = self.websocket_dir / "manager.py"
        if manager_file.exists():
            with open(manager_file) as f:
                content = f.read()
                if "Result[" in content:
                    self.log_pass(
                        "Result type usage",
                        "Manager uses Result types for error handling",
                    )
                if "return Err(" in content:
                    self.log_pass(
                        "Explicit errors",
                        "Manager returns explicit error messages",
                    )

    def print_summary(self) -> None:
        """Print validation summary."""
        print("\n" + "=" * 60)
        print("📊 WEBSOCKET STATIC VALIDATION SUMMARY")
        print("=" * 60)

        total_tests = len(self.results["passed"]) + len(self.results["failed"])
        pass_rate = (
            (len(self.results["passed"]) / total_tests * 100) if total_tests > 0 else 0
        )

        print(f"\n✅ Passed: {len(self.results['passed'])}")
        print(f"❌ Failed: {len(self.results['failed'])}")
        print(f"⚠️  Warnings: {len(self.results['warnings'])}")
        print(f"\n📈 Pass Rate: {pass_rate:.1f}%")

        if self.results["failed"]:
            print("\n❌ Failed Tests:")
            for test, error in self.results["failed"]:
                print(f"   - {test}: {error}")

        print("\n🎯 Requirements Status:")
        requirements = {
            "WebSocket Infrastructure": any(
                "ConnectionManager" in test for test in self.results["passed"]
            ),
            "Real-time Quote Updates": any(
                "broadcast_quote_update" in test for test in self.results["passed"]
            ),
            "Collaborative Features": any(
                "collaborative" in test.lower() for test in self.results["passed"]
            ),
            "Notification System": any(
                "NotificationHandler" in test for test in self.results["passed"]
            ),
            "10,000 Connection Support": any(
                "10,000" in test or "10000" in test for test in self.results["passed"]
            ),
            "Performance Monitoring": any(
                "WebSocketMonitor" in test for test in self.results["passed"]
            ),
        }

        all_met = True
        for req, met in requirements.items():
            status = "✅" if met else "❌"
            print(f"   {status} {req}")
            if not met:
                all_met = False

        if pass_rate >= 85 and all_met:
            print("\n🎉 WebSocket implementation meets Wave 2.5 requirements!")
        else:
            print(
                f"\n⚠️  Implementation at {pass_rate:.0f}% - some requirements need attention."
            )


def main() -> int:
    """Run static validation."""
    print("🚀 Starting WebSocket Static Validation...")
    print("=" * 60)

    validator = WebSocketStaticValidator()

    # Run all validations
    validator.validate_manager()
    validator.validate_handlers()
    validator.validate_monitoring()
    validator.validate_integration()
    validator.validate_database_schema()
    validator.validate_no_silent_fallbacks()

    # Print summary
    validator.print_summary()

    return 0 if len(validator.results["failed"]) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
