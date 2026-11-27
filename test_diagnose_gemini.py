"""Diagnostic commands must not leak keys or unexpectedly generate text."""
from contextlib import redirect_stdout
from io import StringIO
import unittest
from unittest.mock import patch
from config import GeminiConfig
from preference_agent import AIError
import diagnose_gemini


class DiagnosticTests(unittest.TestCase):
    def run_command(self, args, config, info=None, error=None):
        stream = StringIO()
        with patch('sys.argv', ['diagnose_gemini.py'] + args):
            with patch('diagnose_gemini.load_config', return_value=config):
                with patch('diagnose_gemini.gemini_model_info', return_value=info, side_effect=error) as metadata:
                    with patch('diagnose_gemini.parse_preferences', return_value={}) as extraction:
                        with redirect_stdout(stream):
                            status = diagnose_gemini.main()
        self.assertNotIn('fake-secret-key', stream.getvalue())
        return status, stream.getvalue(), metadata, extraction

    def test_default_checks_metadata_without_generation(self):
        status, output, metadata, extraction = self.run_command([], GeminiConfig(api_key='fake-secret-key'),
            {'name':'models/gemini-3.5-flash-lite','supportedGenerationMethods':['generateContent']})
        self.assertEqual(status, 0)
        metadata.assert_called_once()
        extraction.assert_not_called()
        self.assertIn('PASS', output)

    def test_optional_extraction_is_one_call(self):
        status, output, metadata, extraction = self.run_command(['--extract'], GeminiConfig(api_key='fake-secret-key'),
            {'name':'models/gemini-3.5-flash-lite','supportedGenerationMethods':['generateContent']})
        self.assertEqual(status, 0)
        extraction.assert_called_once()

    def test_missing_key_never_contacts_google(self):
        status, output, metadata, extraction = self.run_command([], GeminiConfig(api_key=''))
        self.assertEqual(status, 1)
        metadata.assert_not_called()
        extraction.assert_not_called()

    def test_access_failure_stops_before_generation(self):
        status, output, metadata, extraction = self.run_command(['--extract'], GeminiConfig(api_key='fake-secret-key'),
            error=AIError('Google rejected the key', 503, 'invalid_api_key'))
        self.assertEqual(status, 1)
        self.assertIn('FAIL [invalid_api_key]', output)
        extraction.assert_not_called()


if __name__ == '__main__':
    unittest.main()
