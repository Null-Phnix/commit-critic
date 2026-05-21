import os
import unittest
from unittest.mock import patch

from llm_client import DeepSeekClient, LLMError, OpenAIClient, get_llm_client


class LLMClientTests(unittest.TestCase):
    def test_deepseek_client_uses_deepseek_defaults(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}, clear=True):
            client = DeepSeekClient()

        self.assertEqual(client.api_key, "test-key")
        self.assertEqual(client.base_url, "https://api.deepseek.com")
        self.assertEqual(client.model, "deepseek-v4-flash")
        self.assertEqual(client.get_provider_name(), "deepseek (deepseek-v4-flash)")

    def test_deepseek_client_honors_model_and_base_url_env(self):
        env = {
            "DEEPSEEK_API_KEY": "test-key",
            "DEEPSEEK_MODEL": "deepseek-v4-pro",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com/custom",
        }
        with patch.dict(os.environ, env, clear=True):
            client = DeepSeekClient()

        self.assertEqual(client.model, "deepseek-v4-pro")
        self.assertEqual(client.base_url, "https://api.deepseek.com/custom")

    def test_deepseek_client_requires_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(LLMError, "DEEPSEEK_API_KEY"):
                DeepSeekClient()

    def test_factory_selects_deepseek_provider(self):
        env = {
            "LLM_PROVIDER": "deepseek",
            "DEEPSEEK_API_KEY": "test-key",
        }
        with patch.dict(os.environ, env, clear=True):
            client = get_llm_client()

        self.assertIsInstance(client, DeepSeekClient)

    def test_openai_client_still_uses_openai_defaults(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            client = OpenAIClient()

        self.assertEqual(client.api_key, "test-key")
        self.assertEqual(client.model, "gpt-4o-mini")
        self.assertIsNone(client.base_url)
        self.assertEqual(client.get_provider_name(), "openai (gpt-4o-mini)")


if __name__ == "__main__":
    unittest.main()
