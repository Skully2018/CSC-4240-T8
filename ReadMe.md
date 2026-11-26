# RMR — Roommate Meal Resolutions

RMR recommends meals for households with different tastes, diets, and ingredient restrictions. Gemini interprets written preferences and dish names; TheMealDB supplies recipes. Recommendations use a shared scoring system that considers preference coverage, individual fit, and household ratings.

## Requirements

- Python 3.9 or later
- A current web browser
- Internet access
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

The application uses Python's standard library. No Python packages or local AI model downloads are required.

## Setup

Create a Gemini API key, then open a terminal in the project folder containing `main.py`.

**Windows:**

```powershell
Copy-Item .env.example .env
notepad .env
```

**macOS/Linux:**

```sh
cp .env.example .env
```

Edit `.env` and replace the key placeholder:

```dotenv
GEMINI_API_KEY=your_api_key
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_TIMEOUT_SECONDS=45
```

Keep `.env` beside `main.py`, outside `web/`. Do not overwrite an existing configuration or commit the file to Git.

For free-tier use, select an eligible Google project without billing enabled. Availability and quotas depend on Google's policies and your account. See [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing).

## Run

**Windows:**

```powershell
py -3 main.py
```

You can also double-click `Start RMR.cmd`.

**macOS/Linux:**

```sh
python3 main.py
```

The browser opens automatically. If it does not, use the address printed in the terminal, usually `http://127.0.0.1:8765`. Keep the terminal open while using the app; press Ctrl+C to stop it.

## Usage

Enter a household description, for example:

> Dave likes cheeseburgers and salmon but dislikes broccoli. Jordan likes mozzarella sticks and potatoes, dislikes mushrooms, and is allergic to shellfish.

Click **Find meals with AI**. RMR extracts preferences, infers core dish ingredients, and searches automatically. Unresolved questions pause the search. Use **Edit interpreted household** to correct profiles or **Enter preferences manually** to bypass Gemini.

Dish ingredients are inferred automatically; optional toppings are not assumed. Explicit ingredient preferences take precedence over inferences. Dislikes and allergies are exclusions. Supported diets are Any, Vegetarian, Vegan, Mediterranean, Pescatarian, and Gluten Free, with one diet per person.

Results appear in one ranked list. Ingredient label-check notes remain attached to the relevant meals. Known restriction conflicts are excluded. Fit scores are heuristic preference matches, not safety guarantees; check ingredient labels and cross-contact when preparing food for someone with allergies.

Save recipes in the sidebar and rate meals after trying them. Ratings influence later recommendations. Budget, cooking time, calories, and equipment constraints are not enforced.

## Configuration and storage

| Setting | Default | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | Required for AI input | Private server-side API key |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Model; `gemini-3.1-flash-lite` is also supported |
| `GEMINI_TIMEOUT_SECONDS` | `45` | Request timeout, from 5 to 180 seconds |

Environment variables override `.env`. File changes take effect on the next request. The app does not automatically retry failed requests or switch models.

Household profiles, bookmarks, and ratings are stored in the browser. Use the same browser profile, address, and port to access saved data. There is no shared database or account synchronization.

Descriptions are sent to Google's Gemini API. The API key stays on the Python server. Raw descriptions are not saved by the browser application; evaluation reports do contain their test inputs and outputs. Review the [Gemini API terms](https://ai.google.dev/gemini-api/terms) before submitting sensitive information.

## Tests and evaluation

Run the automated tests from the project folder:

```powershell
py -3 -m unittest -v
```

On macOS/Linux, use `python3` instead of `py -3`. Tests use controlled provider responses and do not require a key or internet access.

To evaluate extraction against the 24 development cases using your API key:

```powershell
py -3 evaluate_extraction.py --interval 7 --output evaluation/results.json
```

Results include extracted profiles, comparison checks, and response times. Adjust request spacing to your quota. These cases are a development set; use separate examples for an independent evaluation.

## Troubleshooting

**Check setup** reports local configuration only. It does not verify API access or remaining quota.

Check model access without generating text:

```powershell
py -3 diagnose_gemini.py
```

Test one extraction request:

```powershell
py -3 diagnose_gemini.py --extract
```

For a missing key, check the `.env` filename and environment overrides. For quota errors, check usage in AI Studio and wait for the relevant limit to reset. Manual entry remains available. Recipe-provider errors require access to TheMealDB independently of Gemini.

See [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) for module descriptions, API behavior, scoring details, and optional browser checks.
