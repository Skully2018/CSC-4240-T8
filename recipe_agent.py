"""Retrieve MealDB candidates and rank the shared evaluator's results."""
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPException
import json
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from household import household
from happiness import ranking_key
from recipe_evaluator import evaluate_candidate


class ProviderError(Exception):
    pass


def fetch(endpoint, params):
    url = 'https://www.themealdb.com/api/json/v1/1/' + endpoint + '.php?' + urlencode(params)
    try:
        req = Request(url, headers={'User-Agent': 'RMR (Roommate Meal Resolutions)'})
        with urlopen(req, timeout=8) as response:
            data = json.load(response)
        if isinstance(data, dict) and 'meals' in data:
            meals = data['meals']
            if meals is None:
                return []
            if isinstance(meals, list):
                # Individual records are validated by the evaluator.
                return meals
    except (OSError, URLError, ValueError, HTTPException) as exc:
        raise ProviderError('TheMealDB could not be reached. Check your connection and try again.') from exc
    raise ProviderError('TheMealDB returned an unexpected response. Please try again.')


def discover(get):
    """Yield complete records from batches of four first-letter requests."""
    letters = 'scabptrmlfgdhkenowiuvjyzqx'
    with ThreadPoolExecutor(max_workers=4) as pool:
        for start in range(0, len(letters), 4):
            batch = list(pool.map(lambda letter: get('search', {'f': letter}), letters[start:start+4]))
            if any(not isinstance(group, list) for group in batch):
                raise ProviderError('TheMealDB returned an unexpected recipe list.')
            yield [row for group in batch for row in group]


def _rating_map(data):
    household_id = data.get('household_id', '')
    if not isinstance(household_id, str) or len(household_id) > 100:
        raise ValueError('Invalid household ID.')
    ratings = data.get('ratings', [])
    if not isinstance(ratings, list) or len(ratings) > 500:
        raise ValueError('Invalid recipe ratings.')
    by_id = {}
    for rating in ratings:
        if not isinstance(rating, dict):
            continue
        meal_id, value = rating.get('meal_id'), rating.get('score')
        if (rating.get('household_id') == household_id and isinstance(meal_id, str)
                and meal_id.isdigit() and isinstance(value, int) and not isinstance(value, bool)
                and 1 <= value <= 5):
            by_id[meal_id] = value
    return by_id


def _select(candidates, limit):
    """Apply the same ranking/discovery policy to any candidate pool."""
    candidates = sorted(candidates, key=lambda item: item[0])
    selected = candidates[:limit]
    selected_ids = {recipe['id'] for _, recipe in selected}
    needed = max(0, min(3, limit) - sum(recipe['prior_rating'] is None for _, recipe in selected))
    exploration = [item for item in candidates if item[1]['prior_rating'] is None
                   and item[1]['id'] not in selected_ids][:needed]
    if exploration:
        selected = selected[:limit - len(exploration)] + exploration
    return [recipe for _, recipe in selected]


def recommend(data, get=fetch, max_attempts=None, max_results=12):
    """One retrieval -> validation -> scoring pipeline for both API routes."""
    if max_attempts is not None and (isinstance(max_attempts, bool)
            or not isinstance(max_attempts, int) or max_attempts < 1):
        raise ValueError('max_attempts must be a positive integer or None.')
    if isinstance(max_results, bool) or not isinstance(max_results, int) or max_results < 1:
        raise ValueError('max_results must be a positive integer.')
    people = household(data)
    ratings = _rating_map(data)
    has_positive = any(item['strength'] > 0 for person in people for item in person['preferences'])
    target_unrated = min(3, max_results)
    ranked, review, rejected = [], [], []
    seen = set()
    attempts = invalid_records = 0
    reached_limit = False
    for rows in discover(get):
        for row in rows:
            raw_id = row.get('idMeal') if isinstance(row, dict) else None
            if isinstance(raw_id, bool) or not isinstance(raw_id, (str, int)) or not str(raw_id).isdigit():
                invalid_records += 1
                continue
            meal_id = str(raw_id)
            if meal_id in seen:
                continue
            if max_attempts is not None and attempts >= max_attempts:
                reached_limit = True
                break
            seen.add(meal_id)
            attempts += 1
            evaluation = evaluate_candidate(row, people)
            status = evaluation['status']
            if status in {'invalid', 'unsafe', 'needs_review'}:
                rejected.append({'id': meal_id,
                                 'title': row.get('strMeal') if isinstance(row.get('strMeal'), str) else '',
                                 'status': status, 'reasons': evaluation['reasons']})
            if status == 'invalid':
                invalid_records += 1
                continue
            if status == 'unsafe':
                continue
            recipe = evaluation['recipe']
            prior = ratings.get(meal_id)
            scores, coverage = evaluation['scores'], evaluation['coverage']
            if has_positive and not scores and (prior is None or prior < 4):
                continue
            base = ranking_key(scores, recipe['title'], meal_id, coverage)
            adjustment = (prior - 3) * 0.025 if prior is not None else 0
            order = (base[0], base[1] - adjustment, *base[2:])
            recipe['prior_rating'] = prior
            (review if status == 'needs_review' else ranked).append((order, recipe))
        if reached_limit or (max_attempts is not None and attempts >= max_attempts):
            break
        if len(ranked) >= max_results and sum(item[1]['prior_rating'] is None for item in ranked) >= target_unrated:
            break
    selected = _select(ranked, max_results)
    recommendations = _select(ranked + review, max_results)
    review.sort(key=lambda item: item[0])
    excluded = sum(item['status'] == 'unsafe' for item in rejected)
    status = 'proposed' if ranked else 'needs_review' if review else 'no_match'
    message = ''
    if not ranked:
        if review:
            message = 'Matching meals include ingredient label-check notes. See each card for details.'
        elif has_positive:
            message = 'No recipes matched the household’s positive taste preferences. Add more liked ingredients or adjust their strengths.'
        elif excluded:
            message = f'No matches. Household restrictions excluded {excluded} recipe(s).'
        elif invalid_records:
            message = 'No complete recipes found. Some provider records were invalid.'
        else:
            message = 'No complete recipes found. Try again later.'
    return {'status': status, 'recipes': selected, 'recommendations': recommendations,
            'review_recipes': [recipe for _, recipe in review[:max_results]],
            'excluded_by_rules': excluded, 'invalid_records': invalid_records,
            'attempts': attempts, 'rejected': rejected, 'message': message}
