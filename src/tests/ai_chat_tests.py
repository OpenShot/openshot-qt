"""
Minimal tests for AI chat: LLM registry and OpenShot tools structure.
Does not require full app or real API keys. Does not call external APIs.
"""

import sys
import os
import unittest

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.insert(0, PATH)


class TestAILLMRegistry(unittest.TestCase):
    """Test LLM registry structure and list_models (no app = empty or default list)."""

    def test_import_registry(self):
        from classes.ai_llm_registry import get_model, list_models, get_default_model_id
        self.assertIsNotNone(get_model)
        self.assertIsNotNone(list_models)
        self.assertIsNotNone(get_default_model_id)

    def test_list_models_returns_list(self):
        from classes.ai_llm_registry import list_models
        result = list_models()
        self.assertIsInstance(result, list)
        for item in result:
            self.assertIsInstance(item, (list, tuple))
            self.assertGreaterEqual(len(item), 2)
            self.assertIsInstance(item[0], str)  # model_id
            self.assertIsInstance(item[1], str)  # display_name

    def test_get_default_model_id_returns_str(self):
        from classes.ai_llm_registry import get_default_model_id
        result = get_default_model_id()
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)


class TestAIProviders(unittest.TestCase):
    """Test provider list and structure."""

    def test_provider_list_non_empty(self):
        from classes.ai_providers import PROVIDER_LIST
        self.assertIsInstance(PROVIDER_LIST, list)
        self.assertGreater(len(PROVIDER_LIST), 0)
        for entry in PROVIDER_LIST:
            self.assertIsInstance(entry, (list, tuple))
            self.assertGreaterEqual(len(entry), 3)
            self.assertTrue(entry[0])  # model_id
            self.assertTrue(entry[1])  # display_name
            self.assertTrue(entry[2])  # provider_module_name


class TestAIOpenShotTools(unittest.TestCase):
    """Test OpenShot tools structure (no app = no execution)."""

    def test_get_openshot_tools_returns_list(self):
        try:
            from classes.ai_openshot_tools import get_openshot_tools_for_langchain
            result = get_openshot_tools_for_langchain()
        except ImportError as e:
            self.skipTest("LangChain not installed: %s" % e)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        for t in result:
            self.assertTrue(hasattr(t, "name") or hasattr(t, "invoke"))
            self.assertTrue(callable(getattr(t, "invoke", None)) or callable(t))


if __name__ == "__main__":
    unittest.main()
