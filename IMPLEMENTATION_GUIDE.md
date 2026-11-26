# RMR Gemini implementation: file and function walkthrough

## 1. What changed

RMR now uses Google's hosted Gemini API for natural-language preference extraction. The default model is `gemini-3.5-flash-lite`, which Google lists with a free tier when this release was prepared. There is no local model download, Ollama dependency, or GPU requirement.

Python and the browser run on the user's computer. The model runs on Google's infrastructure. Your own API key authenticates the HTTPS request. Each person downloading the project supplies their own key; no shared team credential is distributed.

The existing meal-retrieval, diet-screening, and fit-scoring modules retain their algorithms. The AI interprets text into a draft profile. It does not generate recipes or override recipe restrictions.

The original uploaded backend ZIP omitted `web/`. The preceding version reconstructed that frontend. This Gemini version updates that interface and keeps its lavender styling, RMR name, editable review screen, and right-hand saved-meals sidebar.

## 2. Read this before setup

A free-tier-capable model does not force requests to be free. Google associates requests with the project owning the API key. If that project has paid billing enabled, the request can be billable. The API does not provide a `free=true` request option, and RMR cannot inspect or enforce billing tier.

Use an eligible project on Google's Free tier without Cloud billing enabled to avoid paid usage. Check current availability and quotas in AI Studio. RMR makes no automatic model fallback, adds no paid tools, and makes no automatic retries. A quota failure produces a visible error.

The description is sent to Google, including any names and allergies it contains. Google's free-tier terms permit content use to improve products, subject to applicable terms. Prefer nicknames or fictional profiles for evaluation. The app's setup screen discloses this change from local processing.

See `README.md` for exact Windows/macOS/Linux commands. Do not share your real key or private `.env` file.

## 3. Complete file inventory

| File | Role | New/changed for Gemini? |
| --- | --- | --- |
| `main.py` | Starts the local HTTP server and routes API requests | Changed |
| `diagnose_gemini.py` | Checks metadata access, then optionally tests one real extraction without printing secrets | New in diagnostic update |
| `test_diagnose_gemini.py` | Verifies diagnostic call counts and secret omission | New in diagnostic update |
| `config.py` | Reads private Gemini settings and provides non-secret setup status | New |
| `preference_agent.py` | Builds the Gemini request, sends it, validates output, returns an editable draft | Changed |
| `recipe_agent.py` | Validates household input, retrieves MealDB data, screens and ranks meals | Algorithm retained |
| `diet_rules.py` | Ingredient normalization, equivalences, diet rules, allergen checks | Algorithm retained |
| `happiness.py` | Preference matching, per-person scores, household fairness ranking | Algorithm retained |
| `recipe_evaluator.py` | Existing proposal/validation/evaluation endpoint | Algorithm retained |
| `web/index.html` | Description input, setup instructions, profile review, results, bookmarks | Changed |
| `web/app.js` | Browser event handlers, API calls, editable state, rendering, storage | Changed and reformatted for readability |
| `web/style.css` | Lavender colors, responsive layout, forms, cards, sidebar | Retained from preceding natural-language version |
| `.env.example` | Non-secret template users copy to `.env` | New |
| `.gitignore` | Excludes private configuration, Python caches, virtual environments, evaluation outputs | Changed |
| `requirements.txt` | Documents standard-library-only runtime | Changed |
| `Start RMR.cmd` | Windows launcher that changes into its own folder and starts Python | Retained |
| `Start_RMR.sh` | macOS/Linux launcher that changes into its own folder and starts Python | Retained |
| `evaluate_extraction.py` | Runs labeled cases against real Gemini with request spacing | Changed |
| `evaluation/cases.json` | Twenty manually labeled development cases | Retained |
| `test_config.py` | Configuration, key-handling, defaults, validation tests | New |
| `test_preference_agent.py` | Controlled Gemini response, HTTP transport, validation/error tests | Changed |
| `test_http.py` | Endpoint, status, packaged assets, quota, and integrated pipeline tests | Changed |
| `test_diets.py` | Existing diet and ingredient screening tests | Retained |
| `test_happiness.py` | Existing fit/fairness scoring tests | Retained |
| `test_ratings.py` | Existing rating adjustment and discovery tests | Retained |
| `test_recipe_evaluator.py` | Existing Agent 2 validation/search tests | Retained |
| `tools/browser_smoke.py` | Optional Playwright UI check using intercepted provider responses | Changed |
| `README.md` | User setup, use, troubleshooting, APIs/storage overview | Rewritten |
| `IMPLEMENTATION_GUIDE.md` | This detailed architecture, file, and function guide | Rewritten |

A real `.env` is deliberately absent from the distributed archive. No downloaded weights, credentials, virtual environment, or fabricated evaluation results are bundled.

## 4. Configuration: config.py

### Constants

- `BASE_DIR`: the folder containing the Python modules. This ensures `.env` is found even when Python is started from another working directory.
- `DEFAULT_MODEL`: `gemini-3.5-flash-lite`.
- `FREE_TIER_MODELS`: the explicit allowlist containing the default and `gemini-3.1-flash-lite`. These models have documented free tiers; access/pricing still depend on Google and the project. Selecting another model requires a deliberate code change and pricing review.
- `SETTING_NAMES`: the three recognized keys: `GEMINI_API_KEY`, `GEMINI_MODEL`, and `GEMINI_TIMEOUT_SECONDS`.

### ConfigError

An exception for bad local configuration. Messages identify the problem or line number but do not print secret setting values. `parse_preferences()` converts it to a user-facing `AIError`.

### GeminiConfig

An immutable dataclass containing `api_key`, `model`, and `timeout`. The API key uses `repr=False`, so printing the ordinary dataclass representation does not reveal it. This is not a general secret vault; developers must still avoid explicitly logging the field.

### read_env_file(path)

Reads the private configuration as text. It accepts `KEY=value`, optional matching single/double quotes, blank lines, whole-line comments, and UTF-8 with or without a BOM. It rejects unknown names, duplicate settings, and unclosed quotes.

It does not run a shell, evaluate Python, expand `$VARIABLES`, or support shell `export` statements or inline comments. File content is configuration data only.

### load_config(env=None, env_path=None)

1. Reads `.env` beside `main.py`.
2. Applies environment-variable overrides.
3. Treats the example key placeholder as a missing key.
4. Checks key characters without printing the key.
5. Checks the model against the allowlist.
6. Checks that the timeout is an integer between 5 and 180 seconds.
7. Returns `GeminiConfig`.

No key is required merely to start the server. This allows manual entry and recipe search to remain usable. A missing key is rejected only when extraction is requested.

Settings are loaded on each extraction and status request. Editing `.env` takes effect on the next request. Changing an OS environment variable outside an already running process does not modify that process's environment; relaunch in that case.

### public_ai_status()

Returns provider name, configured model, whether a key is present, a readable setup message, and `connection_tested: false`.

It does not return the key, inspect billing, call Google, or consume model quota. “Configured” means local settings exist, not that the key works.

## 5. Language-model integration: preference_agent.py

### AIError

Carries a safe message plus `status`, `code`, and optional `retry_after`. `main.py` uses these to return appropriate JSON errors. Provider error bodies and raw exception strings are not forwarded to the browser because they may contain submitted data or request details.

### array(items, maximum) and obj(properties)

Small helpers that construct the JSON schema. `array()` defines an item type and maximum count. `obj()` requires its declared fields and rejects additional properties.

### SCHEMA

The complete local validation schema requires:

```json
{
  "roommates": [
    {
      "name": "Alex",
      "diet": "Vegetarian",
      "preferences": [
        {"ingredient": "mushrooms", "strength": 2}
      ],
      "avoid": ["olives"],
      "allergies": []
    }
  ],
  "questions": [],
  "unsupported_requests": []
}
```

This is an illustrative contract, not a measured Gemini result. The application permits up to 12 roommates and up to 20 entries in each person's preference, exclusion, and allergy lists. Text lengths are bounded. Diets and preference strengths are enums.

Gemini's supported schema features can differ from full JSON Schema. Python performs its own checks after generation, including length checks that a provider may not enforce. A valid structure does not prove semantic correctness.

### SYSTEM

The extraction prompt defines what each phrase should mean:

| Wording | Intended extraction |
| --- | --- |
| “Rice is fine” | Rice, strength 0 |
| “I like rice” | Rice, strength 1 |
| “I love rice” | Rice, strength 2 |
| “I hate olives” | Olives in `avoid` |
| “Never include olives” | Olives in `avoid` |
| “I am allergic to peanuts” | Peanuts in `allergies` |
| “Dairy bothers me” | Clarification question rather than a diagnosed allergy |
| “Make it under $10” | Unsupported budget request |

The prompt asks the model to extract explicit facts, preserve roommate ownership, avoid inventing additional people, and ask about contradictions. Unnamed people get placeholder names. A person can have only one supported diet in the current data model; incompatible or multiple simultaneous diet statements require clarification rather than silent loss of a restriction.

Budget, cooking time, calories, equipment, texture, spice intensity, and religious certification are not supported by the current search engine. The model should list them under `unsupported_requests`.

The model receives the system instructions separately from the user message. It is instructed to treat embedded instructions in the household description as data. This reduces a common failure mode but does not guarantee resistance to semantic manipulation. It has no external tools or code execution.

### _strict(value, schema, path='output')

Recursively validates every output value. It checks object fields, list sizes, string lengths, integer types, and allowed enum values. Boolean values are explicitly rejected as integer preference strengths.

It catches bad data shapes, not whether a sentence was interpreted correctly. An omitted allergy can still produce structurally valid JSON; the review step and real evaluation are needed for that kind of failure.

### NoRedirect.redirect_request(...)

Prevents automatic HTTP redirects for the Gemini request. This avoids forwarding the custom API-key header to a redirected destination. It returns `None`, causing the redirect response to be handled as an error.

### gemini_generate(payload, config)

Delegates to `_gemini_request(payload, config)`, which makes exactly one HTTPS request to:

```text
https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent
```

The model segment comes from validated configuration. The key is sent in the `x-goog-api-key` HTTP header, not in the URL or JSON body. The request uses standard TLS validation; the code does not disable certificate checking.

The method reads a bounded response, parses its outer JSON, and returns the provider envelope. It does not interpret roommate fields yet.

Error handling:

| Upstream condition | RMR result |
| --- | --- |
| HTTP 400 | HTTP 502, `gemini_request_rejected` |
| HTTP 401/403 | HTTP 503, `gemini_access_denied` |
| HTTP 404 | HTTP 503, `model_unavailable` |
| HTTP 429 | HTTP 429, `quota_exceeded` |
| Other service HTTP errors | HTTP 503, `gemini_service_error` |
| Connection failure/timeout | HTTP 503, `gemini_connection_error` |
| Oversized/non-JSON response | HTTP 502, `invalid_ai_response` |

A simple numeric provider `Retry-After` value is bounded and returned in the JSON error as `retry_after`. RMR does not sleep and retry automatically. It never silently changes to another model.

### _response_text(result)

Reads Gemini's response envelope. It requires exactly one candidate and `finishReason: STOP`. Missing output, truncated generation, malformed parts, and unexpected non-text parts are rejected.

If Gemini explicitly blocks the prompt or candidate, the app returns a readable `ai_blocked` error. If the provider includes thought-marked parts, they are discarded; only final text is parsed into profile data.

### parse_preferences(request, generate=None, config=None)

This is the main agent function and the entry point used by the server and evaluation script.

1. Requires `request` to contain a text string of 1–6,000 characters after trimming.
2. Loads configuration and checks that a key exists.
3. Obtains a nonblocking extraction lock. Another active request produces `ai_busy` rather than a queue of quota-consuming requests.
4. Builds the Gemini request.
5. Calls `gemini_generate()` or an injected test function.
6. Calls `_response_text()` and parses the final JSON.
7. Calls `_strict()`.
8. Calls the existing `recipe_agent.household()` validator for nonempty profiles.
9. Adds a clarification question if no people were extracted and the model returned no question.
10. Returns the validated draft plus metadata; always releases the lock.

The injected `generate` and `config` parameters let tests supply controlled responses and fake credentials without network access. Production calls omit them and use the real transport and local settings.

The Gemini request body uses:

```python
{
    "systemInstruction": {"parts": [{"text": SYSTEM}]},
    "contents": [{"role": "user", "parts": [{"text": description}]}],
    "generationConfig": {
        "temperature": 0,
        "candidateCount": 1,
        "maxOutputTokens": 4096,
        "responseMimeType": "application/json",
        "responseJsonSchema": GEMINI_SCHEMA
    }
}
```

Temperature 0 reduces sampling variability but is not a promise of identical output. The model does not receive recipe-search tools. The 45-second default timeout is configurable.

The endpoint response adds:

- `status`: `ready_for_review` or `needs_clarification`.
- `model`: the configured model name.
- `source`: `gemini_api`.
- `requires_confirmation`: always true.

`ready_for_review` means the model returned no clarification questions. It is not an accuracy or food-safety certification. Existing household normalization also adds the legacy `likes` field for compatibility.

## 6. Local server: main.py

### main()

Parses `--port` and `--no-browser`, creates the threaded HTTP server on `127.0.0.1`, and starts serving. Without an explicit port, it tries ports 8765–8780. It opens the browser after startup unless disabled.

The server binds to loopback. It is designed for a local class application, not direct internet deployment. Hosting it publicly would require proper authentication, request limiting, server deployment, and secret management.

### Handler.end_headers()

Adds `Cache-Control: no-store` so the browser does not retain stale app/API responses through ordinary HTTP caching.

### Handler.reply(status, data)

Serializes Python data to JSON, sets content type and length, and writes the response. AI errors use this same response path.

### Handler.do_GET()

Handles `GET /api/ai-status` by calling `public_ai_status()`. Other GETs use the existing static-file handler rooted in `web/`. The private `.env` lives outside this served directory; the HTTP tests verify `/.env` is not served.

### Handler.do_POST()

Checks the route, supplied browser Origin, JSON content type, and request size. The browser Origin, when present, must match the request Host using the local HTTP origin. This is a local browser cross-origin check, not a complete deployment authentication system.

Routes:

| Request | Function called |
| --- | --- |
| `POST /api/parse-preferences` | `parse_preferences(data)` |
| `POST /api/recommend` | `recommend(data)` |
| `POST /api/evaluate` | `choose_recipe(data, max_attempts=50, max_results=12)` |

Invalid input becomes HTTP 400. Gemini failures preserve the `AIError` status/code. MealDB failures remain HTTP 502 through `ProviderError`.

The browser confirmation workflow is not implemented as a server-side token. Direct API clients can call `/api/recommend` themselves and must provide their own review process.

## 7. Frontend: web/index.html and web/app.js

The HTML defines seven main areas: description input, setup instructions/status, clarification messages, editable profiles, confirmation, recipe results, and saved-meal sidebar. It loads `style.css` and `app.js` without a build step.

The JavaScript is reformatted into readable functions. It has no API key field, Google request, or provider SDK; all provider access goes through Python.

### State

- `draft`: editable profiles from extraction or manual entry.
- `confirmed`: the last profiles saved after a successful recipe-search response.
- `favorites`: recipe bookmarks.
- `ratings`: household-scoped 1–5 recipe ratings.
- `householdId`: a random browser-local identifier used to scope ratings.
- `busy`: prevents overlapping extraction/search actions in this tab.

### DOM helpers

| Function | What it does |
| --- | --- |
| `$()` | Finds a fixed HTML element by ID |
| `node()` | Creates an element and inserts text with `textContent` |
| `control()` | Wraps an input in a label |
| `textInput()` | Creates a text input and clears confirmation on edits |
| `action()` | Creates a button with its click callback |
| `select()` | Creates a dropdown; profile edits clear confirmation, ratings do not |
| `listInput()` | Converts one ingredient per line to a list |
| `showList()` | Shows clarification or unsupported-request messages |
| `externalLink()` | Creates HTTPS-only external links with safe tab attributes |

`textContent` prevents model/recipe text from being inserted as executable HTML. Optional external images are also restricted to HTTPS. Those external providers still receive browser requests when images or links are loaded.

### Profile and extraction functions

| Function | Main calls and behavior |
| --- | --- |
| `extractPreferences()` | Calls `post('/api/parse-preferences', {text})`, replaces `draft`, calls `showList()` and `renderPeople()` |
| `renderPeople()` | Builds editable roommate cards from `draft`; callbacks update profile fields |
| `emptyPerson()` | Returns a blank supported profile with a placeholder name |
| `openManual()` | Shows editable input without an AI call and labels it as manual |
| `addPerson()` | Adds a profile up to the 12-person limit |
| `invalidate()` | Clears confirmation and hides stale recipe results |
| `setBusy()` | Disables conflicting controls while extraction or search is running |
| `post()` | Sends JSON to the local Python server, parses JSON, raises a readable error for failed HTTP responses |
| `checkSetup()` | Calls `GET /api/ai-status` and displays its non-secret local configuration result |

A new extraction replaces the entire draft. It is not a conversational edit or a merge. Users must provide a complete description when re-extracting. They can instead change individual fields directly in the review form.

Clarification questions do not trigger an automatic follow-up model conversation. Users answer them by correcting fields or submitting a revised description. The confirmation checkbox is their explicit attestation that they reviewed the draft and resolved relevant questions; the app does not automatically prove that they did so.

### Search, recipes, and storage functions

| Function | Main calls and behavior |
| --- | --- |
| `findRecipes()` | Requires confirmation, calls `/api/recommend`, saves confirmed profiles, renders result/review cards |
| `card()` | Builds a recipe card with fit, per-person reasons, ingredients, instructions, bookmark button, rating |
| `ratingControl()` | Saves/updates/removes a household's rating for a recipe |
| `renderFavorites()` | Builds the right sidebar from saved bookmarks |
| `save()` | Writes confirmed profiles, bookmarks, ratings, and household ID to localStorage |
| `clearData()` | Asks for browser confirmation, then clears this version's data and resets the UI |

Raw descriptions, AI questions, and unsupported requests are not stored by RMR in localStorage. When the page reloads, it restores saved profiles but leaves confirmation unchecked.

The storage key remains `rmr_natural_language_v1`, preserving the immediately preceding natural-language version's saves. Older pre-natural-language saves are not migrated because their frontend/storage format was not in the uploaded source. The clear button deletes only this version's key.

### Event wiring

At the end of `app.js`, the description's input event calls `invalidate()`. Buttons call the named extraction, manual-entry, add-person, search, clear-data, and setup functions. The file then restores confirmed profiles if present, calls `renderFavorites()`, and calls `checkSetup()` once.

### CSS

`web/style.css` defines typography, lavender colors, form controls, visible keyboard focus, cards, a two-column layout, and a mobile breakpoint at 850px. It does not process data or call APIs. No frontend package installation or build step is required.

## 8. Existing recipe modules and their functions

### recipe_agent.py

| Function/class | Responsibility |
| --- | --- |
| `ProviderError` | Public-facing MealDB provider failure |
| `fetch(endpoint, params)` | Builds the MealDB URL, performs a timed request, checks outer data shape |
| `normalized(text)` | Tokenizes/case-normalizes terms and common plurals for input validation |
| `terms(data, field)` | Checks bounded ingredient lists and normalizes/deduplicates them |
| `household(data)` | Validates 1–12 distinct roommate profiles, diet, strengths, exclusions, and allergies |
| `discover(get)` | Retrieves complete recipe records in batches of four first-letter searches |
| `recommend(data, get=fetch)` | Applies restrictions and fit scoring, separates review candidates, uses ratings, and returns ranked results |

The `get` parameter enables fixture-based tests. Production uses `fetch()`. The AI's output is passed through `household()` before review, and `recommend()` validates the user's final edits through `household()` again.

### diet_rules.py

| Function | Responsibility |
| --- | --- |
| `key(value)` | Normalizes case, accents, punctuation, plurals, and curated equivalents |
| `vocabulary(names)` | Converts a pipe-separated vocabulary into normalized terms |
| `base_name(name)` | Removes recognized preparation prefixes such as chopped/fresh |
| `mentions(text, terms)` | Checks whole-phrase occurrences |
| `screen(people, names, category, recipe_text)` | Applies existing household allergy/diet screening rules |

The module also contains ingredient groups, aliases, known simple ingredients, supported diets, and gluten-free qualification rules. This is a curated screening system, not a universal food-safety database or medical diagnosis system. Labels and cross-contact still need human verification.

### happiness.py

The module has two existing formula families. Their differences are retained rather than silently unified during this provider migration.

| Function | Responsibility |
| --- | --- |
| `matches()` | Matches preference terms to ingredient phrases and known food families |
| `person_score()` | Existing positive-match proportion used by the evaluator's legacy scoring |
| `score_recipe()` | Returns legacy per-person reasons/scores |
| `household_score()` | Blends minimum and average scores with more weight on the minimum |
| `household_happiness()` | Converts that legacy household score to a percentage |
| `ranking_key()` | Sort key for the evaluator's scoring path |
| `score_recipe_for_recommendations()` | Recommendation-specific match points, neutral matches, and unmatched states |
| `household_score_for_recommendations()` | Recommendation-specific household blend and shared-fit bonus |
| `household_happiness_for_recommendations()` | Recommendation-specific displayed percentage |
| `ranking_key_for_recommendations()` | Ranks preference coverage before household fit and stable tie-breakers |

The displayed percentages are heuristic preference-fit scores. They are not experimentally calibrated probabilities that someone will enjoy a meal.

### recipe_evaluator.py

| Function | Responsibility |
| --- | --- |
| `propose_recipes()` | Iterates unique proposals from the existing discovery function |
| `_ingredients()` | Extracts ingredient/measure pairs from a MealDB record |
| `validate_recipe()` | Returns `safe`, `needs_review`, or `unsafe` under existing automated rules |
| `evaluate_happiness()` | Applies the evaluator's existing score calculation |
| `choose_recipe()` | Bounded proposal/validation loop, ranking, and selected-result response |
| Nested `sort_key()` | Builds the final ordering for evaluator candidates |

These status names refer to the program's automated checks, not a guarantee of real-world food safety. The evaluator is available through `/api/evaluate`; the default frontend uses `/api/recommend`.

## 9. Function call sequences

### Setup check

`Check setup` calls `checkSetup()` in JavaScript, which requests `GET /api/ai-status`. `Handler.do_GET()` calls `public_ai_status()`, which calls `load_config()` and returns non-secret configuration status. No model request happens.

### Natural-language extraction

`Review AI preferences` calls `extractPreferences()` in JavaScript. Its `post()` helper sends the description to `/api/parse-preferences`. `Handler.do_POST()` calls `parse_preferences()`. That loads settings, calls `gemini_generate()`, reads output with `_response_text()`, validates it with `_strict()` and `household()`, and returns a draft. JavaScript then calls `showList()` and `renderPeople()`.

### Recipe search

`Confirm & find recipes` calls `findRecipes()`. It checks the confirmation checkbox and calls `/api/recommend`. `Handler.do_POST()` calls `recommend()`. That calls `household()`, `discover()`/`fetch()`, ingredient/rule checks, and recommendation scoring functions. The browser receives recipes, saves confirmed profiles, and calls `card()` to render results.

### Manual fallback

`Enter preferences manually` calls `openManual()` and `renderPeople()`. No Gemini request happens. After review/confirmation, `findRecipes()` uses the same recipe endpoint as the AI-assisted path.

## 10. Tests: what is verified

There are **68 passing Python tests**:

- 10 configuration tests.
- 12 extraction tests.
- 4 Gemini transport tests.
- 6 local HTTP tests.
- 27 original diet/scoring/rating/evaluator tests.
- 5 schema/error regression tests.
- 4 diagnostic command tests.

Configuration tests use temporary fake `.env` data and check defaults, environment precedence, quote handling, malformed settings, model restrictions, timeout bounds, and secret omission.

Extraction tests use fake credentials and controlled Gemini envelopes. They test valid profiles, clarification metadata, missing keys, bad input, invalid fields, incomplete output, blocked requests, ignored thought parts, structured payloads, and lock release.

Transport tests inspect the constructed HTTPS request, header authentication, timeout, redirect refusal, response limits, safe errors, and lack of automatic retries.

HTTP tests check static assets, parse routing, non-secret setup status, inaccessible `.env`, input errors, quota status, and the combined extraction-to-recommendation path. In the combined test, a controlled Gemini response produces a peanut-allergic profile. The actual recommendation pipeline then rejects a fixture recipe with peanuts and retains a compatible rice/mushroom recipe. The provider responses are simulated; profile validation and recipe screening execute normally.

Run tests from the project root:

```powershell
py -3 -m unittest -v
```

Python compilation and JavaScript syntax checks also pass. The application runtime needs no pip packages. Node was used only as a development syntax check.

**No real Gemini call was performed in development because no user API key was configured.** Therefore no real-model accuracy, latency, quota availability, or successful account authentication is claimed. The first single-case evaluation is the user's account-specific live check.

The optional browser smoke test requires:

```powershell
py -3 -m pip install playwright
py -3 -m playwright install chromium
py -3 tools/browser_smoke.py
```

It intercepts AI and recipe responses to test browser flow. Development browser execution remains unverified because the environment did not have a working Chromium binary. HTTP asset checks and syntax checks do not replace visual/interaction verification. Normal app users do not install Playwright.

## 11. Real Gemini evaluation: evaluate_extraction.py

### canonical(people)

Turns profiles into sorted, comparable records. It normalizes names and ingredient terms using the existing `diet_rules.key()` so known equivalents and ordering differences do not create unnecessary exact-match failures.

### main()

Parses:

- `--limit`: 1–20 cases, default 20.
- `--output`: JSON destination, default `evaluation/results.json`.
- `--interval`: seconds between requests, default 7; configurable up to 300.

It loads configuration, requires a key, reads `evaluation/cases.json`, and calls the real `parse_preferences()` for each selected description. It records expected values, actual profiles, latency, automatic checks, and runtime errors. It stops at the first provider/runtime failure without retrying.

The seven-second spacing is a convenience, not a guarantee of satisfying every project's quota. Check AI Studio and increase it if necessary. Daily quotas may require waiting until reset regardless of spacing.

The first 12 cases test unambiguous extraction with complete expected profiles. The remaining eight cover ambiguity or unsupported requests. Automatic checks for those cases measure only the presence of question/unsupported lists; a human must assess whether their content is correct and helpful.

Run one case first, then the full development set:

```powershell
py -3 evaluate_extraction.py --limit 1
py -3 evaluate_extraction.py --interval 7 --output evaluation/results.json
```

Evaluation outputs intentionally contain descriptions and extracted fields, unlike ordinary browser storage. Use fictional data and review files before sharing. The `.gitignore` excludes generated `evaluation/results*.json` by default.

For stronger assignment evidence, create a held-out set not used to refine the prompt. Have teammates independently label it, resolve disagreements, and report exact-match accuracy, per-field errors, explicit allergy/exclusion omissions, invented allergies, clarification quality, runtime errors, and response time. Record model, date, account tier, and evaluation settings. Preserve actual failures and experiments; do not invent abandoned approaches or accuracy numbers.

## 12. Browser storage, API keys, and distribution

The private key exists only in `.env` or the Python process environment. It is sent to Google in an HTTPS header. It is not returned by RMR endpoints, sent to MealDB, embedded in frontend files, or saved in browser localStorage. The app does not log POST bodies or forward raw provider error bodies.

Confirmed household profiles, bookmarks, ratings, and a household ID remain in localStorage. This is per browser profile and origin, including port. There is no account database, multi-device sync, or shared household storage.

The clear-data button resets browser data but does not remove the private server-side key file. To remove API access, delete the key from `.env`/the environment and revoke it in AI Studio if needed.

`.gitignore` protects against accidentally adding ordinary `.env` files to Git, but it is not encryption or access control. Check `git status` and staged diffs before pushing. Do not zip and share a real configured `.env`.

For downloaders, distribute source plus `.env.example`. Each downloader creates a key in their own eligible project. Hosting a shared team backend would be a separate deployment task requiring authenticated access and quota controls.

## 13. Remaining limits and the class demo

- Gemini can omit facts or associate them with the wrong person despite valid JSON.
- The app supports one diet per person and the existing 0/1/2 preference scale; dislikes remain hard exclusions.
- Unsupported meal-planning constraints are displayed but not enforced.
- The browser confirmation is user review, not automated proof of correctness.
- Recipe screening depends on curated vocabularies and provider data.
- Free API access depends on Google's current model/account/region/quota policies.
- Real API access and browser interaction must be checked on the demonstration computer.

Before presenting, configure your key, run the Python tests, run a single real extraction, inspect its profile, and search for a meal. Run the labeled cases early enough to handle quota limits. Present measured results and actual limitations. Describe the AI contribution as natural-language extraction combined with deterministic validation and meal recommendation.

## 14. Official implementation references

- https://ai.google.dev/gemini-api/docs/api-key
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
- https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/api/generate-content
- https://ai.google.dev/gemini-api/docs/rate-limits
- https://ai.google.dev/gemini-api/terms

## 15. HTTP 400 diagnostic update

The first release returned the same generic configuration message for every HTTP 400. An invalid API key can also arrive as HTTP 400, so that message was insufficient for diagnosis. The screenshot of that message alone does not establish the upstream cause.

The previous provider schema contained nested `maxItems` bounds. Google documents that counted array positions multiply the structured-output grammar and can make it too complex, causing HTTP 400. This update removes those provider grammar bounds as a compatibility fix. No successful live run is claimed without the user's own API check.

### generation_schema(schema) and GEMINI_SCHEMA

`generation_schema()` derives a smaller provider schema from `SCHEMA`. It omits string lengths, array counts, additional-property restrictions, and integer enums from the provider grammar. Types, named fields, required fields, and diet string enums remain. The full `SCHEMA` remains in the extraction instructions and `_strict()` still enforces all original limits and allowed values after generation. This does not permit oversized or invalid profiles into recipe search.

### provider_error(exc)

Reads at most 64 KiB of Google's error body, extracts known reason/status/message patterns, and maps them to fixed messages and machine-readable codes. It does not echo raw Google text, arbitrary reason strings, project identifiers, keys, or household descriptions. It distinguishes invalid keys, disabled APIs, key restrictions, schema complexity/rejection, and failed account prerequisites. Unknown errors remain generic and point to the diagnostic command. The error stream is closed after reading.

### _gemini_request(payload, config)

Centralizes transport for both generation and metadata. A non-None payload sends POST `:generateContent`; `None` sends GET to the model metadata endpoint. Both use header authentication, normal TLS checks, redirect refusal, bounded responses, the same timeout, and classified errors. `gemini_generate()` delegates with a payload; `gemini_model_info()` delegates with None.

### diagnose_gemini.main()

Loads settings and prints only the model, whether the key comes from `.env` or an environment override, and fixed PASS/FAIL messages. It verifies the returned model metadata and advertised `generateContent` method. By default it makes no generation request. With `--extract`, a successful metadata check is followed by one fixed fictional extraction through `parse_preferences()`.

Commands:

```powershell
py -3 diagnose_gemini.py
py -3 diagnose_gemini.py --extract
```

A metadata success is not proof of generation quota, schema compatibility, billing tier, or semantic accuracy. An extraction success establishes that the response passed structural/local profile validation. It does not establish whether every intended preference was extracted correctly.

The new regression tests cover schema simplification with unchanged local limits, HTTP 400 key classification, known schema/account failures, secret omission for malformed error bodies, and diagnostic calls that must not generate unless `--extract` was explicitly selected.
