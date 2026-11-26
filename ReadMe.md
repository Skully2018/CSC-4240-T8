# RMR — Roommate Meal Resolutions

Describe the household, let Gemini extract an editable draft, confirm the profiles, and find recipes. The interface uses lavender styling with saved meals on the right.

**This version uses Google's hosted Gemini API. No Ollama, local model download, GPU, or OpenAI account is required.**

## 1. Requirements

- Python 3.9 or later; a currently supported Python release is recommended.
- A current Chrome, Edge, Firefox, or Safari browser.
- Internet access for Gemini and TheMealDB.
- Your own Gemini API key from Google AI Studio.

No pip packages are required for the app, Python tests, or evaluation runner. Python's standard library sends the HTTPS request directly.

## 2. Create your free-tier Gemini key

1. Open https://aistudio.google.com/apikey and sign in to your Google account.
2. Accept the applicable terms and create an API key in a project you control. Depending on your account, AI Studio may create a default project or ask you to choose/create one. Follow its current prompts.
3. Check the project's tier and usage settings. **Use a project on the Free tier without Cloud billing enabled if you want to avoid paid usage.** Do not use a key from a billing-enabled project assuming this program can force it to be free.
4. Copy the key privately. Do not put it in GitHub, screenshots, classroom slides, JavaScript, or chat messages.

Default model: `gemini-3.5-flash-lite`. Google's pricing documentation lists free-tier input/output for this model when this release was prepared. Actual access, regions, quotas, and pricing are controlled by Google and can change. There is no `free=true` API parameter. The app cannot inspect or enforce your project's billing tier.

The app makes one request per extraction click. It does not retry automatically, enable paid tools, or switch models when a request fails. When quota is exhausted it displays an error and offers manual entry.

Free-tier content may be used to improve Google's products under its terms. Use nicknames and fictional household profiles for class evaluation where possible.

## 3. Configure and launch on Windows

Install Python from https://www.python.org/downloads/ if needed. Extract the entire ZIP, then open PowerShell in the extracted **RMR** folder. You should see `main.py`, `.env.example`, and the `web` folder there.

On first setup:

```powershell
Copy-Item .env.example .env
notepad .env
```

Do not repeat the copy command over an already configured `.env`. In Notepad, replace only the key placeholder:

```dotenv
GEMINI_API_KEY=paste_your_actual_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_TIMEOUT_SECONDS=45
```

Save and close Notepad. Keep this file beside `main.py`; do not put it inside `web`. The real file must be named `.env`, not `.env.txt`.

Start the app:

```powershell
py -3 main.py
```

Or double-click **Start RMR.cmd**. Keep the terminal open. If no browser opens, use the printed address, usually http://127.0.0.1:8765. Stop the server using Ctrl+C.

## 4. Configure and launch on macOS/Linux

Install Python 3.9+ if needed, extract the ZIP, and open a terminal in its `RMR` folder:

```sh
cp .env.example .env
```

Edit `.env` in your text editor and replace the key placeholder as shown above. Then:

```sh
python3 main.py
```

`sh Start_RMR.sh` also launches it. Do not overwrite an existing `.env` when repeating setup.

## 5. Check setup and try it

Open **Set up Gemini's free-tier API** in the app and click **Check setup**. It reports whether settings and a key are present. **This does not call Google or verify the key, model access, billing tier, or remaining quota.**

Try this complete description:

> Alex is vegetarian and loves mushrooms. Jordan likes rice and tomatoes, hates olives, and is allergic to peanuts.

1. Click **Review AI preferences**. This sends the description to Google's Gemini API.
2. Read questions and unsupported requests. Edit the draft fields or revise the complete description and extract again.
3. Check every roommate's diet, ingredient preferences, exclusions, and allergies.
4. Check the confirmation box, then click **Confirm & find recipes**.
5. Inspect recipes, fit scores, and ingredients to verify. Save meals and rate them after trying them.

A new extraction replaces the entire draft; it does not merge with earlier profiles. Editing a description or profile clears confirmation. Extraction alone does not save profiles or search recipes. Confirmed profiles are stored after a successful search response.

The model is instructed to treat neutral/like/strong like as strengths 0/1/2. Dislikes become hard exclusions, matching the existing input contract. Only explicit allergies go in the allergy field; ambiguous sensitivities should generate clarification questions. AI can still misunderstand, so user review is required.

Supported diets: Any, Vegetarian, Vegan, Mediterranean, Pescatarian, Gluten Free. One diet per profile is supported. Budget, preparation time, calories, spice intensity, texture, equipment, and religious certifications are not enforced. The model is instructed to flag them as unsupported.

**Enter preferences manually** works even without a key or when Gemini fails. It does not claim to have performed AI extraction.

## 6. Configuration details

| Setting | Meaning |
| --- | --- |
| `GEMINI_API_KEY` | Private key used only by the Python server |
| `GEMINI_MODEL` | Defaults to `gemini-3.5-flash-lite`; `gemini-3.1-flash-lite` is the other explicitly allowed option |
| `GEMINI_TIMEOUT_SECONDS` | HTTP timeout, 5–180 seconds; default 45 |

Environment variables override `.env`. Settings are read on each extraction/setup check, so editing `.env` does not require restarting. Changes to an already running process's external environment do require relaunching it. No third-party dotenv library is needed: `config.py` reads simple `KEY=value` lines, optional matching quotes, blank lines, and whole-line comments. It does not execute the file, expand variables, or support inline comments or shell `export` statements.

Model names are explicitly restricted to two documented free-tier-capable models. This is not a billing guarantee: those same models can also be billed on a paid project. Review current Google pricing before changing the allowed list.

## 7. Tests and real-model evaluation

From the `RMR` folder on Windows:

```powershell
py -3 -m unittest -v
```

On macOS/Linux:

```sh
python3 -m unittest -v
```

**68 automated Python tests pass in development.** They use fake credentials and controlled provider responses; no key or internet is needed. They establish integration/validation behavior, not actual Gemini understanding.

After configuring your own key, try one real evaluation case:

```powershell
py -3 evaluate_extraction.py --limit 1
```

Then run the 20-case development set if quota permits:

```powershell
py -3 evaluate_extraction.py --interval 7 --output evaluation/results.json
```

Use `python3` instead of `py -3` on macOS/Linux. The runner waits seven seconds between calls by default; increase this interval to fit your project's quota. It stops on the first runtime/provider error without automatic retries. Results contain real outputs and timings. No precomputed accuracy results are included.

These examples are a development set. Create separate held-out cases for the report, and manually review ambiguous outputs. See `IMPLEMENTATION_GUIDE.md` for function descriptions, call sequences, and evaluation limitations.

An optional browser smoke test is in `tools/browser_smoke.py`. It requires Playwright as development tooling; normal users do not need it. Its browser responses are mocked, so it is not a live API test.

## 8. Storage and privacy

The API key stays in `.env` or the Python process environment. The app does not send it to browser JavaScript, localStorage, MealDB, or the setup-status response. `.gitignore` excludes `.env`; check staged changes before pushing.

Natural-language extraction is hosted: the complete description, including any names/allergies typed into it, goes to Google's API. It is no longer processed locally by a downloaded model. Review Google's terms before using real personal data.

Confirmed profiles, bookmarks, ratings, and a random household ID remain in this browser's localStorage under `rmr_natural_language_v1`. RMR does not persist the raw description, questions, or unsupported requests. Evaluation results are different: the CLI intentionally saves descriptions and model outputs in a JSON report.

Existing saves from the immediately preceding natural-language version use the same key. Older pre-natural-language saves are not migrated because their frontend/storage format was absent from the original ZIP. Browser profile, address, and port still determine which data is visible. There is no shared database or account synchronization.

## 9. Troubleshooting

### If the older release says “Gemini rejected the request configuration”

That older message collapsed every Google HTTP 400 into the same error. It did not establish whether the problem was the API key, account prerequisites, or output schema. This release simplifies the provider's output grammar and classifies bounded provider error data into fixed, non-secret messages. The full Python validation limits remain in force.

Keep your existing private `.env` when updating. Stop the old server with Ctrl+C, extract the updated ZIP, copy your `.env` into the new `RMR` folder, then restart it.

For a safe diagnostic, run from that folder:

```powershell
py -3 diagnose_gemini.py
```

This checks key/model access using a model-metadata GET request; it does not generate text. It cannot verify billing tier or generation quota. Then, if the metadata check passes:

```powershell
py -3 diagnose_gemini.py --extract
```

That sends one fixed fictional description through the real extraction path and consumes one generation request. It prints success or a safe error code/message, never the key, submitted description, raw provider error body, or extracted profile. A success means structurally valid output, not measured semantic accuracy.

If help is needed, share only the printed `FAIL [...]` line, never `.env` or the key. A `Key source: environment variable` line means an existing `GEMINI_API_KEY` variable overrides the file you edited.


| Message/problem | What to check |
| --- | --- |
| API key missing | Copy `.env.example` to `.env`, replace the placeholder, check `.env.txt` and environment overrides |
| Invalid `.env` setting | Use supported setting names, one per line; no duplicate keys or inline comments |
| Invalid API key | Re-copy a current Gemini key; check whether an environment variable overrides `.env` |
| Schema rejected / too complex | Use the updated simplified-schema release; run the diagnostic with `--extract` |
| Access denied | Verify the key/project, permissions, API restrictions, current key requirements, and regional availability in AI Studio |
| Quota/rate limit | Check AI Studio usage; wait until the relevant quota resets; do not repeatedly click; manual entry remains available |
| Model unavailable | Verify access to the configured model and Google's current model availability; no fallback is automatic |
| Request configuration rejected | Check the model, key eligibility, and API schema settings; retain only non-secret error information when troubleshooting |
| Network error/timeout | Check internet/firewall access to `generativelanguage.googleapis.com`; retry later or use manual entry |
| Invalid/incomplete preferences | Shorten or clarify the description and retry; inspect the editable draft before searching |
| Setup says configured but extraction fails | Setup checks local settings only; the first extraction tests provider access |
| Recipe provider error | Check access to TheMealDB; this is separate from Gemini |
| Saved data missing | Use the same browser profile, hostname, and port; stop an old server before relaunching on port 8765 |

## 10. Code and repository handoff

Copy the complete folder contents into your team's working branch. Keep `web/`, `.env.example`, all Python modules, tests, and docs together. Keep your private `.env` out of Git and distributed ZIPs. Downloaders create their own keys.

Suggested commit message: `Replace local AI with Gemini free-tier preference extraction`

For classroom sources, report methodology, actual evaluation results, limitations, and team contributions. This implementation does not guarantee a grade.

## Official references

- API keys: https://ai.google.dev/gemini-api/docs/api-key
- Pricing and free-tier eligibility: https://ai.google.dev/gemini-api/docs/pricing
- Selected model: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
- Structured outputs: https://ai.google.dev/gemini-api/docs/structured-output
- REST API: https://ai.google.dev/api/generate-content
- Limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Terms: https://ai.google.dev/gemini-api/terms
- MealDB: https://www.themealdb.com/api.php
