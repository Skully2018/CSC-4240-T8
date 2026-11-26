"""Controlled Gemini responses test integration, not real model understanding."""
import copy
import json
from io import BytesIO
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from config import GeminiConfig
from preference_agent import AIError, NoRedirect, _LOCK, GEMINI_SCHEMA, SCHEMA, gemini_generate, parse_preferences, provider_error

CONFIG = GeminiConfig(api_key='fake-test-key')


def profile():
    return {'name':'Alex', 'diet':'Vegetarian',
            'preferences':[{'ingredient':'mushrooms', 'strength':2}],
            'avoid':['olives'], 'allergies':['peanut']}


def response(output):
    return {'candidates':[{'finishReason':'STOP',
                          'content':{'parts':[{'text':json.dumps(output)}]}}],
            'modelVersion':'gemini-3.5-flash-lite',
            'usageMetadata':{'promptTokenCount':100, 'candidatesTokenCount':80}}


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.output = {'roommates':[profile()], 'questions':[], 'unsupported_requests':[], 'dish_suggestions':[]}

    def parse(self, output=None):
        def generate(payload, config):
            return response(self.output if output is None else output)
        return parse_preferences({'text':'Alex loves mushrooms.'}, generate, CONFIG)

    def test_extract_and_reuse_household_normalization(self):
        result = self.parse()
        self.assertEqual(result['roommates'][0]['preferences'][0], {'ingredient':'mushroom', 'strength':2})
        self.assertFalse(result['requires_confirmation'])
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['source'], 'gemini_api')
        self.assertNotIn('fake-test-key', str(result))

    def test_questions_and_unsupported_are_preserved(self):
        self.output['questions'] = ['Is dairy an allergy or a preference?']
        self.output['unsupported_requests'] = ['Budget under $10 is not enforced.']
        result = self.parse()
        self.assertEqual(result['status'], 'needs_clarification')
        self.assertEqual(result['unsupported_requests'], self.output['unsupported_requests'])

    def test_empty_household_requires_question(self):
        self.output['roommates'] = []
        self.assertEqual(self.parse()['status'], 'needs_clarification')

    def test_bad_user_input_never_calls_model(self):
        for data in [None, [], {}, {'text':7}, {'text':' '}, {'text':'x'*6001}]:
            with self.subTest(data_type=type(data).__name__):
                with self.assertRaises(ValueError):
                    parse_preferences(data, lambda *_:self.fail('model called'), CONFIG)

    def test_missing_key_never_calls_model(self):
        with self.assertRaises(AIError) as caught:
            parse_preferences({'text':'Alex likes rice.'}, lambda *_:self.fail('model called'), GeminiConfig(api_key=''))
        self.assertEqual(caught.exception.code, 'ai_not_configured')

    def test_config_error_is_safe_ai_error(self):
        from config import ConfigError
        with patch('preference_agent.load_config', side_effect=ConfigError('Invalid timeout')):
            with self.assertRaises(AIError) as caught:
                parse_preferences({'text':'Alex'})
        self.assertEqual(caught.exception.code, 'ai_configuration')

    def test_reject_invalid_or_unexpected_model_values(self):
        variants = []
        for field, value in [('diet','Keto'), ('allergies','peanut'), ('name',''),
                             ('avoid',['x'*81]), ('preferences',[{'ingredient':'rice','strength':True}])]:
            item = copy.deepcopy(self.output)
            item['roommates'][0][field] = value
            variants.append(item)
        item = copy.deepcopy(self.output); item['roommates'] *= 2; variants.append(item)
        item = copy.deepcopy(self.output); item['roommates'][0]['preferences'][0]['strength'] = -2; variants.append(item)
        item = copy.deepcopy(self.output); item['unexpected'] = 'value'; variants.append(item)
        item = copy.deepcopy(self.output); item['questions'] = ['x'*301]; variants.append(item)
        variants.extend([None, [], {'roommates':[]}])
        for item in variants:
            with self.subTest(item_type=type(item).__name__):
                with self.assertRaises(AIError):
                    parse_preferences({'text':'Alex'}, lambda *_:response(item), CONFIG)

    def test_bad_envelope_truncated_and_non_json(self):
        variants = [None, [], {}, {'candidates':[]}, {'candidates':[None]},
                    {'candidates':[{'finishReason':'MAX_TOKENS'}]},
                    {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'not json'}]}}]},
                    {'candidates':[{'finishReason':'STOP','content':{'parts':[{'functionCall':{}}]}}]}]
        for item in variants:
            with self.subTest(item_type=type(item).__name__):
                with self.assertRaises(AIError) as caught:
                    parse_preferences({'text':'Alex'}, lambda *_:item, CONFIG)
                self.assertEqual(caught.exception.code, 'invalid_ai_response')

    def test_blocked_prompt_and_candidate_have_clear_errors(self):
        for item in [{'promptFeedback':{'blockReason':'SAFETY'}},
                     {'candidates':[{'finishReason':'SAFETY'}]}]:
            with self.assertRaises(AIError) as caught:
                parse_preferences({'text':'Alex'}, lambda *_:item, CONFIG)
            self.assertEqual(caught.exception.code, 'ai_blocked')
            self.assertEqual(caught.exception.status, 422)

    def test_thought_parts_are_ignored(self):
        result = response(self.output)
        result['candidates'][0]['content']['parts'].insert(0, {'thought':True,'text':'private thought'})
        parsed = parse_preferences({'text':'Alex'}, lambda *_:result, CONFIG)
        self.assertNotIn('private thought', str(parsed))

    def test_request_is_structured_has_no_tools_or_key_in_body(self):
        seen = []
        def generate(payload, config):
            seen.append(payload)
            self.assertIs(config, CONFIG)
            return response(self.output)
        parse_preferences({'text':'Alex loves mushrooms.'}, generate, CONFIG)
        payload = seen[0]
        self.assertEqual(payload['generationConfig']['responseMimeType'], 'application/json')
        self.assertEqual(payload['generationConfig']['responseJsonSchema']['type'], 'object')
        self.assertEqual(payload['contents'][0]['parts'][0]['text'], 'Alex loves mushrooms.')
        self.assertNotIn('tools', payload)
        self.assertNotIn('fake-test-key', json.dumps(payload))

    def test_busy_and_lock_released_after_error(self):
        _LOCK.acquire()
        try:
            with self.assertRaises(AIError) as caught:
                self.parse()
            self.assertEqual(caught.exception.code, 'ai_busy')
        finally:
            _LOCK.release()
        with self.assertRaises(AIError):
            parse_preferences({'text':'Alex'}, lambda *_:{}, CONFIG)
        self.assertEqual(self.parse()['status'], 'ready')


class SchemaAndErrorRegressionTests(unittest.TestCase):
    def test_remote_schema_omits_grammar_expanding_limits(self):
        def check(schema):
            for field in ('maxItems', 'minLength', 'maxLength', 'additionalProperties'):
                self.assertNotIn(field, schema)
            if schema['type'] == 'integer':
                self.assertNotIn('enum', schema)
            for value in schema.get('properties', {}).values():
                check(value)
            if 'items' in schema:
                check(schema['items'])
        check(GEMINI_SCHEMA)
        self.assertEqual(SCHEMA['properties']['roommates']['maxItems'], 12)
        self.assertEqual(GEMINI_SCHEMA['required'], SCHEMA['required'])

    def test_local_limits_still_reject_oversized_model_lists(self):
        for people in [[dict(profile(), name='Person '+str(i)) for i in range(13)],
                       [dict(profile(), preferences=[{'ingredient':'rice','strength':1}]*21)]]:
            output = {'roommates':people, 'questions':[], 'unsupported_requests':[], 'dish_suggestions':[]}
            with self.assertRaises(AIError) as caught:
                parse_preferences({'text':'Alex likes rice'}, lambda *_:response(output), CONFIG)
            self.assertEqual(caught.exception.code, 'invalid_ai_response')

    def make_error(self, message, status='INVALID_ARGUMENT', reason=None):
        error = {'message':message, 'status':status}
        if reason:
            error['details'] = [{'reason':reason}]
        return HTTPError('url', 400, 'Bad request', {}, BytesIO(json.dumps({'error':error}).encode()))

    def test_http400_invalid_key_is_not_misreported_as_schema_failure(self):
        error = provider_error(self.make_error('private text fake-test-key', reason='API_KEY_INVALID'))
        self.assertEqual(error.code, 'invalid_api_key')
        self.assertNotIn('fake-test-key', str(error))
        self.assertIn('environment variable', str(error))

    def test_schema_complexity_and_account_errors_are_distinct(self):
        for failure, expected in [
            (self.make_error('The specified schema produces too many states for serving.'), 'schema_too_complex'),
            (self.make_error('Unknown responseJsonSchema setting'), 'schema_rejected'),
            (self.make_error('private account details', 'FAILED_PRECONDITION'), 'gemini_failed_precondition'),
            (self.make_error('private data', reason='SERVICE_DISABLED'), 'api_not_enabled'),
            (self.make_error('private data', reason='API_KEY_HTTP_REFERRER_BLOCKED'), 'api_key_restricted')
        ]:
            error = provider_error(failure)
            self.assertEqual(error.code, expected)
            self.assertNotIn('private', str(error))

    def test_unknown_or_malformed_error_body_is_not_exposed(self):
        for body in [b'not json with fake-secret-key', b'x'*65537,
                     json.dumps({'error':{'message':'my private household fake-secret-key'}}).encode(), b'[]']:
            error = provider_error(HTTPError('url', 400, 'fake-secret-key', {}, BytesIO(body)))
            self.assertEqual(error.code, 'gemini_request_rejected')
            self.assertNotIn('fake-secret-key', str(error))
            self.assertIn('diagnose_gemini.py', str(error))


class TransportTests(unittest.TestCase):
    def test_https_header_auth_timeout_and_json_response(self):
        stream = MagicMock()
        stream.__enter__.return_value.read.return_value = b'{"candidates": []}'
        with patch('preference_agent.build_opener') as opener:
            opener.return_value.open.return_value = stream
            self.assertEqual(gemini_generate({'contents':[]}, CONFIG), {'candidates':[]})
            req = opener.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url, 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent')
            self.assertEqual(req.get_header('X-goog-api-key'), 'fake-test-key')
            self.assertNotIn('fake-test-key', req.full_url)
            self.assertEqual(opener.return_value.open.call_args.kwargs['timeout'], 45)
            self.assertEqual(json.loads(req.data), {'contents':[]})
            opener.return_value.open.assert_called_once()

    def test_http_errors_do_not_echo_provider_body_or_retry(self):
        mapping = {400:'gemini_request_rejected', 401:'gemini_access_denied', 403:'gemini_access_denied',
                   404:'model_unavailable', 429:'quota_exceeded', 500:'gemini_service_error', 503:'gemini_service_error'}
        for status, code in mapping.items():
            with self.subTest(status=status):
                with patch('preference_agent.build_opener') as opener:
                    opener.return_value.open.side_effect = HTTPError('url', status, 'fake-secret-key', {'Retry-After':'30'}, None)
                    with self.assertRaises(AIError) as caught:
                        gemini_generate({}, CONFIG)
                    self.assertEqual(caught.exception.code, code)
                    self.assertNotIn('fake-secret-key', str(caught.exception))
                    opener.return_value.open.assert_called_once()
                    if status == 429:
                        self.assertEqual(caught.exception.status, 429)
                        self.assertEqual(caught.exception.retry_after, 30)

    def test_connection_and_json_errors(self):
        with patch('preference_agent.build_opener') as opener:
            opener.return_value.open.side_effect = URLError('fake-secret-key')
            with self.assertRaises(AIError) as caught:
                gemini_generate({}, CONFIG)
            self.assertEqual(caught.exception.code, 'gemini_connection_error')
            self.assertNotIn('fake-secret-key', str(caught.exception))
        for raw in [b'not json', b'x'*262145]:
            with patch('preference_agent.build_opener') as opener:
                opener.return_value.open.return_value.__enter__.return_value.read.return_value = raw
                with self.assertRaises(AIError) as caught:
                    gemini_generate({}, CONFIG)
                self.assertEqual(caught.exception.code, 'invalid_ai_response')

    def test_redirects_are_not_followed(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example'))


if __name__ == '__main__':
    unittest.main()
