import json
import threading
import unittest
from functools import partial
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from config import GeminiConfig
from recipe_agent import recommend
from main import Handler, WEB
from preference_agent import AIError


class QuietHandler(Handler):
    def log_message(self,*_):pass


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(WEB)))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def request(self,path,body=None,headers=None,method='POST'):
        conn=HTTPConnection(*self.server.server_address,timeout=3)
        conn.request(method,path,body,headers or {'Content-Type':'application/json'})
        res=conn.getresponse();status=res.status;data=res.read();conn.close();return status,data

    def test_frontend_assets_are_packaged(self):
        for path in ['/','/app.js','/style.css']:
            self.assertEqual(self.request(path,method='GET')[0],200)

    def test_parse_route(self):
        with patch('main.parse_preferences',return_value={'status':'ready_for_review'}) as parse:
            status,data=self.request('/api/parse-preferences',json.dumps({'text':'Alex likes rice'}))
            self.assertEqual(status,200);self.assertEqual(json.loads(data)['status'],'ready_for_review')
            parse.assert_called_once_with({'text':'Alex likes rice'})

    def test_gemini_extraction_flows_into_real_recipe_pipeline(self):
        profiles = [{'name':'Alex', 'diet':'Vegetarian',
                     'preferences':[{'ingredient':'rice','strength':1}],
                     'avoid':['olives'], 'allergies':['peanut']}]
        output = {'roommates':profiles, 'questions':[], 'unsupported_requests':[]}
        gemini = {'candidates':[{'finishReason':'STOP', 'content':{'parts':[{'text':json.dumps(output)}]}}]}
        meals = [
            {'idMeal':'1', 'strMeal':'Peanut rice', 'strCategory':'Vegetarian',
             'strInstructions':'Cook rice with peanuts.', 'strIngredient1':'rice', 'strIngredient2':'peanut'},
            {'idMeal':'2', 'strMeal':'Mushroom rice', 'strCategory':'Vegetarian',
             'strInstructions':'Cook rice with mushrooms.', 'strIngredient1':'rice', 'strIngredient2':'mushroom'}
        ]
        with patch('preference_agent.load_config', return_value=GeminiConfig(api_key='fake-private-key')):
            with patch('preference_agent.build_opener') as opener:
                opener.return_value.open.return_value.__enter__.return_value.read.return_value = json.dumps(gemini).encode()
                status, body = self.request('/api/parse-preferences', json.dumps({'text':'Alex is vegetarian, likes rice, hates olives, and is allergic to peanuts.'}))
        self.assertEqual(status, 200)
        extracted = json.loads(body)
        self.assertNotIn('fake-private-key', str(extracted))
        with patch('main.recommend', side_effect=lambda data:recommend(data, get=lambda *_:meals)):
            status, body = self.request('/api/recommend', json.dumps({'roommates':extracted['roommates']}))
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual([recipe['id'] for recipe in result['recipes']], ['2'])
        self.assertEqual(result['excluded_by_rules'], 1)

    def test_status_does_not_expose_key_or_call_provider(self):
        with patch('config.load_config') as config:
            config.return_value.api_key = 'fake-private-key'
            config.return_value.model = 'gemini-3.5-flash-lite'
            status, data = self.request('/api/ai-status', method='GET')
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(data)['configured'])
        self.assertNotIn(b'fake-private-key', data)
        self.assertEqual(self.request('/.env', method='GET')[0], 404)

    def test_quota_status_is_preserved(self):
        with patch('main.parse_preferences', side_effect=AIError('Quota exceeded', 429, 'quota_exceeded', 30)):
            status, data = self.request('/api/parse-preferences', '{}')
        self.assertEqual(status, 429)
        self.assertEqual(json.loads(data)['retry_after'], 30)

    def test_errors(self):
        self.assertEqual(self.request('/api/parse-preferences','not json')[0],400)
        self.assertEqual(self.request('/api/parse-preferences','{}',{'Content-Type':'text/plain'})[0],415)
        self.assertEqual(self.request('/api/parse-preferences','{}',{'Content-Type':'application/json','Origin':'https://other.example'})[0],403)
        self.assertEqual(self.request('/api/missing','{}')[0],404)
        with patch('main.parse_preferences',side_effect=AIError('Gemini API key missing')):
            status,data=self.request('/api/parse-preferences','{}')
            self.assertEqual(status,503);self.assertEqual(json.loads(data)['message'],'Gemini API key missing')


if __name__=='__main__':unittest.main()
