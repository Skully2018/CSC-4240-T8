import json,sys,threading
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
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  people=[dict(name='Alex',diet='Vegetarian',preferences=[dict(ingredient='rice',strength=1)],avoid=['olives'],allergies=[])]
  parsed=dict(roommates=people,questions=['Please verify the exclusion.'],unsupported_requests=['Budget is not enforced.'],model='gemini-3.5-flash-lite')
  page.route('**/api/parse-preferences',lambda route:route.fulfill(json=parsed))
  meal=dict(id='123',title='<script>test</script> Rice',happiness=78,reasons=[dict(name='Alex',happiness=78,matched=['rice'])],ingredients=[dict(name='rice',measure='1 cup')],instructions='Cook rice.',url='https://www.themealdb.com/meal/123',review_notes=[])
  requests=[]
  def recommend(route):
   requests.append(route.request.post_data_json)
   route.fulfill(json=dict(recipes=[meal],review_recipes=[],excluded_by_rules=1,message=''))
  page.route('**/api/recommend',recommend)
  page.goto(f'http://127.0.0.1:{server.server_port}')
  page.locator('#description').fill('Alex is vegetarian, likes rice and hates olives.')
  page.locator('#extract').click();page.locator('#people .person').wait_for()
  assert page.locator('#questions').is_visible()
  assert page.locator('#unsupported').is_visible()
  page.locator('#search').click();assert not requests
  page.locator('#confirm').check();page.locator('#search').click()
  page.locator('#cards article').wait_for()
  assert requests[0]['roommates'][0]['avoid']==['olives']
  assert page.locator('#cards h3').inner_text()=='<script>test</script> Rice'
  page.get_by_role('button',name='Save favorite',exact=True).click()
  assert page.locator('#favorites .saved').count()==1
  page.locator('#cards select').select_option('5')
  page.reload();assert page.locator('#people .person').count()==1
  assert page.locator('#favorites .saved').count()==1
  assert page.locator('#favorites select').input_value()=='5'
  assert not page.locator('#confirm').is_checked()
  page.locator('#confirm').check();page.locator('#people input').first.fill('Alex edited')
  assert not page.locator('#confirm').is_checked()
  page.set_viewport_size({'width':390,'height':844})
  assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
  page.route('**/api/parse-preferences',lambda route:route.fulfill(status=503,json={'message':'Gemini API key missing'}))
  page.locator('#description').fill('Alex loves rice');page.locator('#extract').click()
  page.get_by_text('Gemini API key missing',exact=True).wait_for()
  page.locator('#manual').click();assert page.locator('#review').is_visible()
  assert not errors,errors
  print('PASS: extraction review, questions, unsupported requests, confirmation, submitted profiles, escaped output, recipe search, favorites, ratings, reload, edit invalidation, mobile width, AI error and manual fallback. API responses mocked; no live model or MealDB requests.')
  browser.close()
finally:server.shutdown();server.server_close()
