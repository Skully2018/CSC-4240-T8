# RMR implementation and function guide

## 1. Architecture

RMR converts a written household description into editable profiles using Gemini, then retrieves and evaluates MealDB recipes. Ordinary inputs search automatically after extraction; interpreted profiles remain optionally editable. Unresolved questions pause the automatic search.

There is one active meal pipeline:

1. `recipe_agent.recommend()` validates the household and retrieves candidate records.
2. Each unique candidate passes to `recipe_evaluator.evaluate_candidate()`.
3. The evaluator normalizes provider data, applies restrictions, and calls the canonical scoring functions in `happiness.py`.
4. The recipe agent ranks the evaluator's accepted/review candidates, applies small rating adjustments, and returns results.

`/api/evaluate` delegates to this same pipeline. It does not run an independent search implementation or use a different happiness formula. The legacy singular `recipe` response field remains available and never selects a review candidate.

Gemini performs text extraction. Python validates profiles and performs recipe screening/scoring. The displayed percentages are heuristic preference-fit scores, not calibrated satisfaction or safety probabilities.

## 2. Installation and account requirements

Follow `README.md` to install Python, create a Gemini API key, copy `.env.example` to `.env`, and launch the application. The app uses only Python's standard library; no pip packages, local model download, Ollama, or GPU are required.

The default is `gemini-3.5-flash-lite`; `gemini-3.1-flash-lite` is also explicitly allowed. These were documented free-tier-capable models when this release was prepared. Google controls availability, eligibility, quotas, and pricing. The app cannot inspect or enforce billing tier. Use an eligible Free-tier project without Cloud billing enabled to avoid paid usage.

The complete description goes to Google, including names/restrictions typed into it. Use nicknames or fictional class-evaluation profiles where possible. Review Google's terms for free-tier processing. Each downloader supplies their own key; never distribute a configured `.env`.

## 3. File inventory

| File | Responsibility |
| --- | --- |
| `main.py` | Local HTTP server, API routing, static frontend files |
| `config.py` | Private Gemini settings and non-secret configuration status |
| `household.py` | Shared profile validation, normalization, preference deduplication |
| `preference_agent.py` | Gemini extraction, schemas, validation, classified provider errors |
| `recipe_agent.py` | MealDB retrieval, shared evaluator orchestration, ratings, ranking |
| `recipe_evaluator.py` | Provider record normalization, restriction/review checks, candidate scoring |
| `happiness.py` | One canonical fit-scoring and ranking formula |
| `diet_rules.py` | Culinary normalization, specific/category matching, dietary/allergen rules |
| `web/index.html` | Description, setup, review, results, saved-meal markup |
| `web/app.js` | Browser workflow, editable state, ratings/bookmarks, localStorage |
| `web/style.css` | Lavender styling and responsive layout |
| `diagnose_gemini.py` | Metadata check, optional one-call extraction check |
| `evaluate_extraction.py` | Real-model evaluation runner with request spacing |
| `evaluation/cases.json` | Twenty-four labeled development descriptions |
| `test_config.py` | Configuration defaults, validation, and secret omission |
| `test_diagnose_gemini.py` | Diagnostic call counts and secret omission |
| `test_preference_agent.py` | Controlled model responses, transport/errors, schema regressions |
| `test_http.py` | Server endpoints, assets, error responses, integration |
| `test_diets.py` | Existing dietary/exclusion/allergy checks |
| `test_happiness.py` | Canonical preference/fairness scoring behavior |
| `test_ratings.py` | Rating adjustments and unrated discovery |
| `test_recipe_evaluator.py` | Evaluator restrictions, unique candidates, bounded search |
| `test_dish_suggestions.py` | Dish inference, automatic application, explicit preference precedence, ownership, restrictions, and profile limits |
| `test_recommendation_visibility.py` | Higher-fit label-note meals remain visible while hard conflicts stay excluded |
| `test_pipeline.py` | Shared-route consistency, exact/category matching, duplicates, malformed records |
| `tools/browser_smoke.py` | Optional Playwright workflow test with intercepted API responses |
| `.env.example` | Non-secret configuration template |
| `.gitignore` | Excludes secrets, environments, caches, generated evaluation outputs |
| `requirements.txt` | Documents standard-library-only runtime |
| `Start RMR.cmd` | Windows launcher |
| `Start_RMR.sh` | macOS/Linux launcher |
| `README.md` | Setup, usage, tests, and troubleshooting |
| `IMPLEMENTATION_GUIDE.md` | This file/function guide |

The archive excludes the real `.env`, Python caches, downloaded models, and fabricated evaluation results.

## 4. Configuration functions: config.py

- `GeminiConfig`: immutable settings object containing key, model, timeout. The ordinary dataclass representation omits the key.
- `ConfigError`: readable configuration failure without secret values.
- `read_env_file(path)`: reads supported `KEY=value` settings, whole-line comments, optional matching quotes, and blank lines. It rejects duplicates/unknown settings and never executes or expands file content.
- `load_config(env=None, env_path=None)`: reads `.env` beside the Python modules, applies environment overrides, validates model/key/timeout, and returns settings. A placeholder is treated as no key. Timeout is 5–180 seconds, default 45.
- `public_ai_status()`: reports model, whether a key is present, and a non-secret message. It does not call Google, verify the key, inspect billing, or consume generation quota.

Editing `.env` takes effect on the next request. Environment values override it; changing a parent shell's variables does not alter an already-running Python process.

## 5. Shared household validation: household.py

- `terms(data, field)`: accepts up to 20 ingredient terms, validates their types/lengths, normalizes culinary equivalents, and deduplicates them.
- `household(data)`: accepts 1–12 uniquely named profiles, validates supported diets and strengths 0/1/2, normalizes ingredients, and deduplicates preferences by canonical ingredient.

Repeated preferences contribute once. If synonyms/repetitions state different nonnegative strengths, the strongest is retained independent of input order. Exclusions/allergies remain separate. The compatibility `likes` field contains positive ingredients.

Both model output and user-edited search input use this validator. `recipe_agent.household` remains importable as a re-export for existing team code, but the implementation resides only here.

## 6. Gemini extraction: preference_agent.py

### Schema and prompt

`array()` and `obj()` construct `SCHEMA`, the full local validation contract. It permits up to 12 roommates, each with up to 20 preferences/exclusions/allergies, bounded strings, supported diet values, and strengths 0/1/2.

`generation_schema()` derives `GEMINI_SCHEMA` by omitting string lengths, array counts, additional-property restrictions, and integer enums from the provider grammar. This avoids unnecessarily complex constrained decoding. The full constraints remain in the instructions and local `_strict()` validator.

`SYSTEM` asks Gemini to extract explicit facts, preserve roommate ownership, ask about ambiguity/conflicts, and identify unsupported requests. Neutral/like/strong like map to 0/1/2. Dislikes become hard exclusions. Ambiguous sensitivities require questions rather than invented diagnoses.

Supported diets are Any, Vegetarian, Vegan, Mediterranean, Pescatarian, Gluten Free. The current schema holds one diet per person. Budget, cooking time, calories, equipment, spice intensity, texture, and religious certifications are not enforced by recipe search; the prompt asks Gemini to flag them.

Positive/neutral dish preferences produce separate `dish_suggestions`, each containing an existing roommate's name, a dish name, up to eight core ingredients, and strength. `review_dish_suggestions()` normalizes/deduplicates these entries, rejects unknown ownership, and filters known personal restriction conflicts. The response adds `excluded_ingredients` for the review display. `apply_dish_suggestions()` then merges allowed core ingredients into the profile automatically. Explicit preferences always win; shared inferred ingredients deduplicate with maximum inferred strength. It records `applied_ingredients`, never changes allergies/exclusions, and raises a clarification question if the profile limit prevents adding all inferred preferences.

The prompt uses cheeseburger -> beef/cheese/bread as a core-ingredient example, omits optional toppings, and asks about ambiguous cuisines or disliked dishes. Actual model quality still requires live evaluation.

The output contract is:

```json
{
  "roommates": [{
    "name": "Alex",
    "diet": "Vegetarian",
    "preferences": [{"ingredient": "mushroom", "strength": 2}],
    "avoid": ["olive"],
    "allergies": []
  }],
  "questions": [],
  "unsupported_requests": [],
  "dish_suggestions": []
}
```

This is an illustration, not a recorded model result. Valid JSON can still misunderstand the description; users can correct the interpretation in the optional editor.

### Transport and errors

- `AIError`: safe message, HTTP status, machine-readable code, optional numeric retry delay.
- `NoRedirect.redirect_request()`: refuses redirects so the key header is not forwarded to another destination.
- `_gemini_request(payload, config)`: sends one HTTPS request with `x-goog-api-key` header and bounded response size. A payload sends POST `:generateContent`; None sends model metadata GET. Normal TLS checks remain enabled.
- `gemini_generate()`: thin generation entry point.
- `gemini_model_info()`: thin metadata entry point.
- `provider_error()`: reads bounded error data, classifies known conditions, and returns fixed messages without forwarding raw bodies or arbitrary provider text.

Known error codes distinguish invalid keys, disabled API, key restrictions, unavailable models, account prerequisites, schema rejection/complexity, quota limits, connection failures, and invalid responses. No automatic retries, model fallback, or paid tools are enabled.

### Extraction entry point

`parse_preferences(request, generate=None, config=None)`:

1. Validates 1–6,000 characters of text and loads settings.
2. Requires a key and takes a nonblocking extraction lock.
3. Builds system instructions, user contents, and generation settings: one candidate, temperature 0, 4,096 output-token cap, JSON MIME type, simplified JSON schema.
4. Calls `gemini_generate()` or the controlled test substitute.
5. `_response_text()` accepts one completed STOP candidate, ignores thought-marked parts, and handles explicit blocking.
6. `_strict()` validates complete local types, counts, lengths, fields, and enum values.
7. `household()` normalizes/deduplicates valid profiles.
8. Returns the draft, questions, unsupported requests, model/source, and `requires_confirmation: false`.

The lock is released even on failure. `ready` means no clarification questions were returned; it does not establish semantic correctness. Temperature 0 is not a reproducibility guarantee.

## 7. Recipe retrieval: recipe_agent.py

- `ProviderError`: controlled external recipe-provider failure.
- `fetch(endpoint, params)`: timed MealDB HTTPS request and outer-list validation. Individual records pass to the evaluator for field validation.
- `discover(get)`: retrieves first-letter batches with four workers. An unexpected batch type becomes a controlled provider error.
- `_rating_map(data)`: validates rating-container input and retains valid household-scoped 1–5 ratings by recipe ID.
- `recommend(data, get=fetch, max_attempts=None, max_results=12)`: validates household/limits, deduplicates candidate IDs, calls `evaluate_candidate()` for every candidate, then ranks accepted/review results.

Default discovery stops when enough eligible recipes and unrated options are found, or after all letters. It is a bounded provider search, not a guarantee of globally optimal ranking over every MealDB record. Explicit positive `max_attempts` bounds unique candidates when requested.

Ratings make a small ordering adjustment after mandatory screening; highly rated prior meals may remain even without current taste matches. Up to three unrated results are retained when available, limited by `max_results`.

The `_select()` helper applies shared ranking/exploration to each pool. Responses include `recommendations` (one combined ranking of screened and review candidates), legacy recipes/review partitions, rule exclusions, invalid-record count, attempted unique IDs, rejection reasons, and a readable message. Invalid records are not counted as dietary violations. ID-less invalid records are counted as encountered because they cannot be reliably deduplicated by recipe ID.

## 8. Candidate evaluation: recipe_evaluator.py

- `normalize_recipe(row)`: checks ID, required text fields, optional metadata types, populated ingredient names/measures, and at least one ingredient. It creates a normalized record without changing the provider dictionary.
- `_validate_normalized(recipe, people)`: one shared restriction/review implementation. Checks allergies, category-aware exclusions, diet rules, unsupported allergen terms, and uncertain ingredient labels/composition.
- `validate_recipe(row, people)`: public raw-record validation entry point using the same normalization/checks.
- `_score_normalized(recipe, people)`: calls canonical `score_recipe()` and `household_happiness()` and computes roommate coverage.
- `evaluate_happiness(row, people)`: direct helper using that same score path; malformed records raise ValueError.
- `evaluate_candidate(row, people)`: active pipeline entry point. Normalizes once, screens once, scores acceptable/review candidates once, and constructs the result card. Invalid/unsafe candidates never become recommendation cards.
- `choose_recipe(request, get=None, max_attempts=None, max_results=12)`: compatibility wrapper over `recommend()`. It adds singular `recipe` and preserves `no_verified_recipe` for an otherwise empty no-match result. It never selects a review candidate as the singular recipe.

The evaluator's states are invalid, unsafe, needs_review, or safe under automated checks. These refer to program screening rather than a real-world safety guarantee. Labels and cross-contact still require verification.

The wrapper's import of `recommend()` is local to avoid a module cycle. It does not create a second retrieval algorithm. With identical inputs and limits, both endpoints return identical lists/scores.

## 9. Matching and fit: diet_rules.py and happiness.py

`diet_rules.key()` normalizes case, accents, common plurals, and curated culinary equivalents. `vocabulary()`, `base_name()`, and `mentions()` support vocabulary construction, preparation-prefix removal, and whole-phrase checks.

`food_terms()` expands only explicitly generic categories: fish, shellfish, seafood, dairy, cheese, nuts/tree nuts, and gluten. Specific salmon, cheddar, shrimp, or almond terms do not expand to unrelated allergen-family members. True synonyms such as shrimp/prawn and aubergine/eggplant remain equivalent. The same category semantics apply to taste preferences and always-exclude terms.

Allergy screening in `screen()` retains its separate conservative family expansion. Changes to taste matching do not weaken that screening. Existing dietary vocabularies and qualified gluten-free/plant alternatives remain in use.

`happiness.py` has one formula family:

- `matches()`: normalized ingredient phrases with explicit generic-category expansion.
- `score_recipe()`: personal fit/reasons. Direct callers also receive preference deduplication protection.
- `household_score()`: minimum/mean blend plus shared-fit bonus.
- `household_happiness()`: percentage conversion or None when unscored.
- `ranking_key()`: coverage, household fit, minimum fit, and deterministic title/ID ties.

The working recommendation formula is preserved: matched preference points are 0.03/0.08/0.10 for neutral/like/strong like, added to a 0.62 baseline with the existing list-size adjustment and 0.90 cap. Unknown personal scores display as unscored; when some profiles match, their household contribution uses the existing 0.70 baseline. The household blend weights the minimum by 0.6 and mean by 0.4, adding the existing shared-fit bonus at full coverage.

Names ending in `_for_recommendations` remain simple aliases to these exact function objects for existing imports. They do not contain alternate implementations. The legacy percentage-of-liked-ingredients formula and its negative-strength branch have been removed.

## 10. Server calls: main.py

`main()` handles port/browser arguments, binds the threaded server to `127.0.0.1`, and optionally opens a browser. It tries ports 8765–8780 unless a port is explicit. This is a local application server, not a production internet deployment.

`Handler.end_headers()` disables ordinary HTTP caching. `reply()` serializes JSON responses. `do_GET()` serves non-secret `/api/ai-status` or static files rooted in `web/`. The private `.env` is outside that directory.

`do_POST()` checks route, supplied Origin, content type, and request size. Routes:

| Route | Call |
| --- | --- |
| `/api/parse-preferences` | `parse_preferences(data)` |
| `/api/recommend` | `recommend(data)` |
| `/api/evaluate` | `choose_recipe(data)` -> `recommend(data)` |

Input failures are HTTP 400; Gemini uses its classified AIError status/code; recipe-provider failures are HTTP 502. There is no mandatory browser confirmation checkbox. API callers can inspect the same extracted profiles and recipe label-check metadata.

## 11. Browser functions and state: web/app.js

State consists of editable and last-saved profiles, bookmarks, ratings, household ID, and a busy flag. A new extraction replaces the draft. Edits hide stale results. Inferences are applied on the server; there is no pending-dish counter or manual add/skip gate. Extraction automatically calls recipe search if profiles exist and no unresolved questions remain. Questions stay visible and open the editor; unsupported requests remain visibly unenforced.

| Function(s) | Purpose |
| --- | --- |
| `$`, `node`, `control` | Fixed-element lookup, text-safe element creation, labels |
| `textInput`, `action`, `select`, `listInput` | Input/button/dropdown/list controls and change callbacks |
| `save`, `invalidate`, `setBusy` | Persistence, stale-result invalidation, overlapping-action prevention |
| `renderDishSuggestions` | Shows a collapsed informational explanation of automatically inferred ingredients and omitted conflicts |
| `showList`, `renderPeople` | Clarifications/unsupported requests and editable profiles |
| `post` | JSON requests to the local Python server, readable error propagation |
| `extractPreferences` | Parse endpoint, optional profile editor, then automatic search when unambiguous |
| `emptyPerson`, `addPerson`, `openManual` | Unique placeholder names and manual fallback |
| `externalLink` | HTTPS-only external links |
| `ratingControl`, `syncRatingControls` | Rate/update/clear a meal and immediately synchronize every visible control for that recipe |
| `card`, `renderFavorites` | Recipe results, review notes, ingredient details, bookmarks/sidebar |
| `findRecipes` | Call recommend, persist profiles, render the unified recommendations list with inline label notes |
| `clearData` | Confirm and reset this app's browser data |
| `checkSetup` | Visible progress/completion time for a local configuration check; no Gemini call |

`textContent` avoids inserting model/provider output as HTML. External images/links use HTTPS. The current browser must support structuredClone, crypto.randomUUID, and inert.

The HTML defines the screens/controls and loads JavaScript/CSS without a build step. CSS supplies lavender styles, focus states, cards, and an 850px mobile breakpoint.

## 12. Storage and distribution

The API key stays in `.env` or the Python environment and goes to Google only in the HTTPS authentication header. It is not returned to JavaScript, sent to MealDB, or saved in localStorage. Error bodies and POST contents are not logged by RMR.

The browser stores confirmed profiles after a successful search, bookmarks, household-scoped ratings, and a random household ID under `rmr_natural_language_v1`. Raw descriptions/questions/unsupported lists are not persisted there. Origin, port, and browser profile determine access. There is no shared database/synchronization.

Existing saves remain compatible. Duplicate preferences in older saved profiles normalize during the next search and are saved in corrected form afterward. Clearing browser data does not remove the server-side `.env`.

Keep `.env` untracked. `.gitignore` is not encryption and does not untrack a previously committed secret. Check staged changes before publishing. Each downloader copies `.env.example` and creates their own key.

## 13. Diagnostics and evaluation

`diagnose_gemini.main()` reads configuration and checks model metadata access without generating text. `--extract` adds one fixed fictional extraction after metadata succeeds. Output uses non-secret PASS/FAIL messages. Success does not establish semantic accuracy or billing tier.

`evaluate_extraction.canonical()` creates normalized, sorted profile comparisons. Its `main()` supports `--limit`, `--output`, and `--interval`, calls real extraction, records actual output/timing/checks, and stops on runtime/provider failure. Default spacing is seven seconds, which must be adjusted to the project's quota.

The 24 labeled examples are a development set. The first 12 check complete unambiguous profiles. Ambiguous cases check clarification/unsupported lists; their meaning needs human review. Four additional dish cases cover cheeseburgers, explicit exclusions alongside dish preferences, negative dish preferences, and broad cuisine requests. The runner also compares proposed dish ingredients separately from explicit profiles. Evaluation JSON intentionally contains descriptions and extracted data, unlike ordinary browser persistence.

For assignment evidence, add a held-out set, independently label it, report field/exact-match errors, allergy/exclusion omissions, clarification quality, runtime failures, and latency. Preserve actual failed examples and prompt experiments. Do not invent results or abandoned approaches.

## 14. Verification and limits

There are **110 Python tests** covering configuration, Gemini extraction/transport/errors, HTTP routing, diet rules, scoring, ratings, evaluator behavior, and shared-pipeline regressions. Tests use controlled responses/fake credentials; they do not make real Gemini or MealDB requests.

New regressions verify identical endpoint scoring/lists, evaluator participation in the live recommendation path, canonical score aliases, specific/category matching, preserved allergy screening, duplicate preference handling, invalid provider records, optional null fields, and nonmutation of provider data.

JavaScript syntax, controlled rating-control checks, and controlled automatic-search/clarification checks also pass. The optional Playwright script checks broader browser behavior, including both-direction rating synchronization, but has not run here because no working Chromium binary is installed. It requires optional development packages; app users do not need them.

No live Gemini call was made in this environment because no user key is configured. Verify one real extraction and the browser flow on the demonstration computer. Fixture-based tests do not establish real-model extraction accuracy.

## 15. Official references

- API keys: https://ai.google.dev/gemini-api/docs/api-key
- Pricing: https://ai.google.dev/gemini-api/docs/pricing
- Structured outputs: https://ai.google.dev/gemini-api/docs/structured-output
- REST generation: https://ai.google.dev/api/generate-content
- Rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Terms: https://ai.google.dev/gemini-api/terms
- MealDB: https://www.themealdb.com/api.php
