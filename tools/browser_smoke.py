"""Optional browser workflow check; API responses are controlled fixtures."""
import sys
import threading
from pathlib import Path
from functools import partial
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from http.server import ThreadingHTTPServer
from main import Handler,WEB
from playwright.sync_api import sync_playwright

server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(WEB)))
threading.Thread(target=server.serve_forever,daemon=True).start()
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1280,'height':900})
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        people=[dict(name='Alex',diet='Vegetarian',preferences=[dict(ingredient='rice',strength=1)],avoid=['olives'],allergies=[])]
        parsed=dict(roommates=people,questions=[],unsupported_requests=['Budget is not enforced.'],dish_suggestions=[],model='gemini-3.5-flash-lite')
        page.route('**/api/parse-preferences',lambda route:route.fulfill(json=parsed))
        meal=dict(id='123',title='<script>test</script> Rice',happiness=78,reasons=[dict(name='Alex',happiness=78,matched=['rice'])],ingredients=[dict(name='rice',measure='1 cup')],instructions='Cook rice.',url='https://www.themealdb.com/meal/123',review_notes=['Check the sauce label.'],verification_status='needs_review')
        requests=[]
        def recommend(route):
            requests.append(route.request.post_data_json)
            route.fulfill(json=dict(recipes=[],review_recipes=[meal],recommendations=[meal],excluded_by_rules=1,message=''))
        page.route('**/api/recommend',recommend)
        page.goto(f'http://127.0.0.1:{server.server_port}')
        page.locator('#description').fill('Alex is vegetarian, likes rice and hates olives.')
        page.locator('#extract').click()
        page.locator('#cards article').wait_for()
        assert len(requests)==1
        assert page.locator('#unsupported').is_visible()
        assert page.locator('#cards h3').inner_text()=='<script>test</script> Rice'
        assert page.get_by_text('Check the sauce label.',exact=True).is_visible()
        assert not page.locator('#review').evaluate('(element)=>element.open')
        page.get_by_role('button',name='Save favorite',exact=True).click()
        page.locator('#cards select').select_option('5')
        assert page.locator('#favorites select').input_value()=='5'
        page.locator('#favorites select').select_option('4')
        assert page.locator('#cards select').input_value()=='4'
        page.reload()
        assert page.locator('#favorites select').input_value()=='4'
        page.locator('#review > summary').click()
        page.locator('#people input').first.fill('Alex edited')
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        # An inference is already applied by the server; no add/skip controls.
        people[0]['preferences'].append(dict(ingredient='cheese',strength=1))
        parsed['dish_suggestions']=[dict(name='Alex',dish='cheese sandwich',ingredients=['cheese','bread'],strength=1,excluded_ingredients=[],applied_ingredients=['cheese'])]
        page.locator('#description').fill('Alex likes rice and cheese sandwiches.')
        page.locator('#extract').click()
        page.locator('#cards article').wait_for()
        page.get_by_text('How dishes were interpreted',exact=True).wait_for()
        assert page.locator('#dish-suggestions button').count()==0
        # Real unresolved questions pause automatic search.
        parsed['questions']=['Which roommate has the allergy?']
        page.locator('#description').fill('One roommate has an allergy.')
        previous=len(requests)
        page.locator('#extract').click()
        page.get_by_text('Which roommate has the allergy?',exact=True).wait_for()
        assert len(requests)==previous
        page.route('**/api/parse-preferences',lambda route:route.fulfill(status=503,json={'message':'Gemini API key missing'}))
        page.locator('#description').fill('Alex likes rice.')
        page.locator('#extract').click()
        page.get_by_text('Gemini API key missing',exact=True).wait_for()
        page.locator('#manual').click()
        assert page.locator('#review').is_visible()
        assert not errors,errors
        print('PASS: automatic search, visible label-note meals, optional editing, dish explanations, clarification pause, bookmarks/ratings, mobile width, and manual fallback. API responses mocked.')
        browser.close()
finally:
    server.shutdown()
    server.server_close()
