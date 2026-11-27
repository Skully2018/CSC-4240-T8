"""Configuration tests use fake credentials and never contact Google."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from config import ConfigError, DEFAULT_MODEL, GeminiConfig, load_config, public_ai_status


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.path = Path(self.temp.name) / '.env'

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_file_allows_manual_mode(self):
        config = load_config(env={}, env_path=self.path)
        self.assertEqual(config.api_key, '')
        self.assertEqual(config.model, DEFAULT_MODEL)
        self.assertEqual(config.timeout, 45)

    def test_file_supports_comments_quotes_and_utf8_bom(self):
        self.path.write_text('\ufeff# Private configuration\nGEMINI_API_KEY="fake-file-key"\nGEMINI_MODEL=gemini-3.1-flash-lite\nGEMINI_TIMEOUT_SECONDS=30\n', encoding='utf-8')
        config = load_config(env={}, env_path=self.path)
        self.assertEqual(config.api_key, 'fake-file-key')
        self.assertEqual(config.model, 'gemini-3.1-flash-lite')
        self.assertEqual(config.timeout, 30)

    def test_environment_overrides_file(self):
        self.path.write_text('GEMINI_API_KEY=fake-file-key\n')
        config = load_config(env={'GEMINI_API_KEY': 'fake-env-key'}, env_path=self.path)
        self.assertEqual(config.api_key, 'fake-env-key')

    def test_placeholders_are_missing_credentials(self):
        config = load_config(env={'GEMINI_API_KEY':'paste_your_key_here'}, env_path=self.path)
        self.assertEqual(config.api_key, '')

    def test_bad_file_reports_line_without_secret_value(self):
        for content in ['GEMINI_API_KEY=fake-secret\nGEMINI_API_KEY=duplicate-secret',
                        'UNKNOWN=fake-secret', 'GEMINI_API_KEY="unclosed-secret', 'no equals']:
            with self.subTest(content_type=content.split('=')[0]):
                self.path.write_text(content)
                with self.assertRaises(ConfigError) as caught:
                    load_config(env={}, env_path=self.path)
                self.assertNotIn('secret', str(caught.exception))

    def test_timeout_validation(self):
        for value in ['0', '181', 'forty', '5.5']:
            with self.subTest(value=value):
                with self.assertRaises(ConfigError):
                    load_config(env={'GEMINI_TIMEOUT_SECONDS':value}, env_path=self.path)

    def test_invalid_key_is_not_echoed(self):
        for value in ['fake key', 'fake\nkey', 'x'*513]:
            with self.assertRaises(ConfigError) as caught:
                load_config(env={'GEMINI_API_KEY':value}, env_path=self.path)
            self.assertNotIn(value, str(caught.exception))

    def test_unsupported_model_does_not_fallback(self):
        with self.assertRaises(ConfigError):
            load_config(env={'GEMINI_MODEL':'some-paid-model'}, env_path=self.path)

    def test_config_repr_and_public_status_never_expose_key(self):
        config = GeminiConfig(api_key='fake-secret-key')
        self.assertNotIn('fake-secret-key', repr(config))
        with patch('config.load_config', return_value=config):
            status = public_ai_status()
        self.assertTrue(status['configured'])
        self.assertFalse(status['connection_tested'])
        self.assertNotIn('fake-secret-key', str(status))

    def test_public_status_handles_configuration_error(self):
        with patch('config.load_config', side_effect=ConfigError('Invalid timeout')):
            self.assertFalse(public_ai_status()['configured'])


if __name__ == '__main__':
    unittest.main()
