# RMR — Roommate Meal Resolutions

On Windows, extract the ZIP and double-click **Start RMR.cmd**. Alternatively run `py main.py` from the extracted folder. On macOS or Linux use `python3 main.py`. Requires Python 3.9+ and internet access. Leave the terminal open while using the app. If a browser tab does not open, use the local URL printed in the terminal (usually http://127.0.0.1:8765). Stop a previous copy with Ctrl+C before starting this version to reuse the same port and browser saves.

## Find meals

Enter each roommate’s name, diet, ingredient taste preferences, allergies, and ingredients to always exclude. Set each taste preference from strong dislike to strong like. **Find recipes** opens a separate screen. Results show household and per-roommate fit scores with colors. Use **Ingredients to verify** to inspect uncertain ingredients. Use **Edit household** to change preferences. Household entries autosave to this browser. **Save favorite** adds a MealDB bookmark to the **Saved recipes** sidebar on the household screen. You can also rate a recipe after trying it; ratings are stored in this browser separately from bookmarks and can influence future ordering. Use the same browser profile, address and port to restore saves. The original household and favorite browser keys preserve data across the RMR rename.

## How search works

RMR retrieves full MealDB recipe records in batches of four first-letter requests, filtering as it goes. It continues until it has enough eligible recipes and some unrated options, or has requested all 26 letters. A recipe ID is considered once. The response shows up to 12 ranked matches and up to 12 separate review candidates. Ingredient preferences influence ordering; zero-fit meals are not presented as matches when positive household tastes are listed. “Always exclude” entries, allergies, and diet rules are hard screening rules. Household ratings provide additional feedback, while some unrated choices remain available for discovery. Exact scoring weights are not shown in the user interface.

Names are normalized for case, accents, punctuation and common plurals. A curated vocabulary handles variants including eggplant, egg plant, aubergine, brinjal, berenjena, melanzana, patlıcan and baingan. The agent checks the title, ingredient names, measures and instructions. A conflict in any of them removes the recipe before ranking. This dictionary covers named equivalents; it is not a general translator. See EQUIVALENTS in diet_rules.py to add vocabulary.

## Rules used by the app

| Diet | Screening rule |
| --- | --- |
| Any | Apply the household’s dislikes and allergy checks. |
| Vegetarian | Exclude recognized land meat, seafood, gelatin and rennet. Permit eggs and dairy. Screen ingredients even when the category says Vegetarian. |
| Vegan | Apply vegetarian exclusions plus recognized dairy, eggs and honey. Recognize common plant alternatives such as coconut milk. |
| Pescatarian | Permit fish, shellfish, eggs, dairy and plant foods. Exclude recognized land meats and their stocks. |
| Mediterranean | Use a meal-level approximation. Require two groups among vegetables, legumes, whole grains, olives/olive oil, fish/shellfish and tree nuts, including at least one of the first three. Screen out listed red or processed meat. |
| Gluten Free | Screen recipe text for wheat, barley, rye, malt and common derivatives. Exclude ordinary bread, pasta and unlabeled oats. Recognize qualified forms such as rice flour and gluten-free oats. If the composition of another ingredient is uncertain, show it for label review. |

Vegetarian, vegan and pescatarian searches also consider meals in general categories such as Side. Uncertain ingredients outside a diet-compatible category trigger review. Multiple roommates’ rules apply together. Recognized allergens and listed aliases are hard exclusions. When an allergy term has no established family rule, literal conflicts are removed and remaining candidates require review. Ingredient screening cannot verify packaged labels or kitchen cross-contact. A qualified gluten-free ingredient can still conflict with a separate wheat allergy.

## Sources and maintenance

- Gluten-free foods and label checks: https://celiac.org/gluten-free-living/gluten-free-foods/
- Plant-based diets: https://www.vegansociety.com/go-vegan/definition-veganism
- Pescatarian diet: https://health.clevelandclinic.org/pescatarian-diet
- Mediterranean eating pattern: https://www.heart.org/en/healthy-living/healthy-eating/eat-smart/nutrition-basics/mediterranean-diet
- Eggplant terminology: https://dictionary.cambridge.org/dictionary/english/aubergine
- MealDB educational API and first-letter endpoint: https://www.themealdb.com/api.php

## Team integration

The Recipe Agent is the recommendation component inside RMR. Import `recommend` from `recipe_agent.py` or POST JSON to /api/recommend, for example:

```json
{"roommates":[{"name":"Mike","diet":"Gluten Free","likes":["rice"],"avoid":["eggplant"],"allergies":[]}]}
```

The response includes status, recipes, review_recipes, and excluded_by_rules. Each review card explains the specific checks still needed. Run `py -m unittest -v` from the project folder to check the screening and retrieval regressions.

## Replace the Docker stand-in on dev

These PowerShell steps use a fresh checkout so local work in any existing clone stays intact. You need Git, GitHub write access or a pull request, and the extracted RMR folder. The folder you copy from should contain main.py, README.md and web directly.

1. Clone the team's dev branch in a parent directory of your choice.

   ```powershell
   git clone --branch dev https://github.com/Skully2018/CSC-4240-T8.git RMR-dev
   cd RMR-dev
   git status --short --branch
   ```

   Expect dev tracking origin/dev. If the clone reports that dev does not exist, check the branch name with your team.

2. Set the source path and check that you selected the right folder. Replace the example path if needed.

   ```powershell
   $rmrSource = "$env:USERPROFILE\Downloads\RMR"
   Get-ChildItem -LiteralPath $rmrSource
   ```

3. Inspect the tracked setup files. The uploaded project used Dockerfile, compose.yaml, recipe_kb.sql and requirements.txt exclusively for the stand-in. If the current dev branch uses any of them for another component, retain that file. Otherwise run the removal command below. Git retains their history.

   ```powershell
   git ls-files
   git rm --ignore-unmatch -- Dockerfile compose.yaml recipe_kb.sql requirements.txt
   ```

4. Normalize the old ReadMe.md spelling if present and copy the release into the repository root. This keeps the repository's .git folder, .gitignore and unrelated files intact. Review any overlapping work on dev when you inspect the diff.

   ```powershell
   if ((git ls-files) -ccontains 'ReadMe.md') {
       git mv ReadMe.md rmr-readme-temp.md
       git mv rmr-readme-temp.md README.md
   }
   $rmrFiles = 'README.md','Start RMR.cmd','main.py','recipe_agent.py','diet_rules.py','test_diets.py'
   foreach ($name in $rmrFiles) {
       Copy-Item -LiteralPath (Join-Path $rmrSource $name) -Destination . -Force
   }
   New-Item -ItemType Directory -Force web | Out-Null
   foreach ($name in 'index.html','style.css','app.js') {
       Copy-Item -LiteralPath (Join-Path $rmrSource "web\$name") -Destination web -Force
   }
   ```

5. Test the checkout and inspect the staged change. In the app, generate a recipe, save a favorite, and return to the household screen to check the sidebar. Press Ctrl+C to stop.

   ```powershell
   py -m unittest -v
   py main.py
   git add -- README.md "Start RMR.cmd" main.py recipe_agent.py diet_rules.py test_diets.py web/index.html web/style.css web/app.js
   git diff --cached --stat
   git diff --cached
   ```

6. Commit and push once the diff contains the intended changes. If Git rejects a push because dev moved, fetch and reconcile the new commits before retrying. If dev requires pull requests, push your existing commit to a topic branch and open a pull request with dev as its base.

   ```powershell
   git commit -m "Replace Docker stand-in with RMR roommate meal app"
   git push origin dev
   ```

   For a protected dev branch:

   ```powershell
   git switch -c rmr-ui-integration
   git push -u origin rmr-ui-integration
   ```

## Handoff for the next UX/UI developer

Two proposed features extend the current ranking. Both are future work.

- **Ingredient preference strength.** Give each ingredient a labeled slider or numeric selector from −2 (strong dislike) through 0 (neutral) to +2 (strong like). Keep a separate “Always exclude” control. Preserve existing saved dislikes as exclusions during migration and keep allergies and diet rules mandatory. Apply preference weights only to eligible recipes, and retain the least-satisfied-roommate ranking so one enthusiastic rating cannot dominate the household.
- **Rate a recipe after trying it.** Offer an optional 1–5 rating beside each result or saved recipe. Store the MealDB recipe ID, a stable roommate or household ID, score and timestamp. Let people revise or remove a rating. Use prior feedback as a small ranking adjustment after hard exclusions. Give unrated meals a neutral starting point and keep a few unfamiliar options in the results. Keep bookmarks separate from ratings so saving a dish to try does not count as liking it.
