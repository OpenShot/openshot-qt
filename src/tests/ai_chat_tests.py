"""
Minimal tests for AI backend integration: API client, model listing, and tool structure.
Does not require a running backend — tests client construction and structure only.
For integration tests that need the backend, set ZENVI_BACKEND_URL.
"""

import sys
import os
import unittest

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.insert(0, PATH)


class TestAPIClient(unittest.TestCase):
    """Test the ZenviBackendClient can be imported and constructed."""

    def test_import_client(self):
        from classes.api_client import ZenviBackendClient, get_backend_client
        self.assertIsNotNone(ZenviBackendClient)
        self.assertIsNotNone(get_backend_client)

    def test_client_construction(self):
        from classes.api_client import ZenviBackendClient
        client = ZenviBackendClient(base_url="http://localhost:9999")
        self.assertIn("http://localhost:9999", client.api_url)

    def test_empty_ai_metadata_structure(self):
        from classes.api_client import ZenviBackendClient
        meta = ZenviBackendClient._empty_ai_metadata()
        self.assertIsInstance(meta, dict)
        self.assertFalse(meta["analyzed"])
        self.assertIn("scene_descriptions", meta)
        self.assertIn("tags", meta)


class TestToolHandlers(unittest.TestCase):
    """Test that tool_handlers module can be imported and has the expected structure."""

    def test_import_tool_handlers(self):
        from classes.tool_handlers import execute_tool, TOOL_HANDLERS
        self.assertIsNotNone(execute_tool)
        self.assertIsInstance(TOOL_HANDLERS, dict)
        self.assertGreater(len(TOOL_HANDLERS), 0)

    def test_all_handlers_are_callable(self):
        from classes.tool_handlers import TOOL_HANDLERS
        for name, handler in TOOL_HANDLERS.items():
            self.assertTrue(callable(handler), f"{name} is not callable")

    def test_unknown_tool_returns_error(self):
        from classes.tool_handlers import execute_tool
        result = execute_tool("nonexistent_tool_xyz", {})
        self.assertIn("Error", result)


if __name__ == "__main__":
    unittest.main()
