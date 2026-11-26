'use strict';

// The browser calls our Python server. Only Python knows the Gemini API key.
const $ = id => document.getElementById(id);
const KEY = 'rmr_natural_language_v1';
const diets = ['Any', 'Vegetarian', 'Vegan', 'Mediterranean', 'Pescatarian', 'Gluten Free'];
let stored = {};
try {
  stored = JSON.parse(localStorage.getItem(KEY) || '{}') || {};
} catch (_) {
  // An unavailable or malformed browser save must not block a new session.
}
let confirmed = Array.isArray(stored.roommates) ? stored.roommates : [];
let favorites = Array.isArray(stored.favorites) ? stored.favorites : [];
let ratings = Array.isArray(stored.ratings) ? stored.ratings : [];
let householdId = typeof stored.household_id === 'string' ? stored.household_id : crypto.randomUUID();
let draft = [];
let busy = false;

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function save() {
  try {
    localStorage.setItem(KEY, JSON.stringify({roommates: confirmed, favorites, ratings, household_id: householdId}));
  } catch (_) {
    $('notice').textContent = 'Browser storage is unavailable. This session still works, but changes may not persist.';
  }
}

function invalidate() {
  $('confirm').checked = false;
  $('results').hidden = true;
}

function control(label, input) {
  const wrapper = node('label', label);
  wrapper.append(input);
  return wrapper;
}

function textInput(value, change, maximum = 80) {
  const input = node('input');
  input.value = value;
  input.maxLength = maximum;
  input.addEventListener('input', () => {
    change(input.value);
    invalidate();
  });
  return input;
}

function action(text, callback, secondary = true) {
  const button = node('button', text, secondary ? 'secondary' : '');
  button.type = 'button';
  button.addEventListener('click', callback);
  return button;
}

function select(values, value, change, editing = true) {
  const input = node('select');
  for (const [optionValue, label] of values) {
    const option = node('option', label);
    option.value = optionValue;
    input.append(option);
  }
  input.value = String(value);
  input.addEventListener('change', () => {
    change(input.value);
    if (editing) invalidate();
  });
  return input;
}

function listInput(values, change) {
  const input = node('textarea');
  input.rows = 2;
  input.value = values.join('\n');
  input.placeholder = 'One ingredient per line';
  input.maxLength = 1700;
  input.addEventListener('input', () => {
    change(input.value.split('\n').map(value => value.trim()).filter(Boolean));
    invalidate();
  });
  return input;
}

function renderPeople() {
  $('people').replaceChildren();
  draft.forEach((person, index) => {
    const box = node('div', undefined, 'person');
    box.append(node('h3', `Roommate ${index + 1}`));
    const grid = node('div', undefined, 'grid');
    grid.append(
      control('Name', textInput(person.name, value => person.name = value, 50)),
      control('Diet', select(diets.map(value => [value, value]), person.diet, value => person.diet = value))
    );
    box.append(grid, node('h4', 'Ingredient preferences'));
    person.preferences.forEach((preference, preferenceIndex) => {
      const row = node('div', undefined, 'preference');
      const ingredient = textInput(preference.ingredient, value => preference.ingredient = value);
      ingredient.setAttribute('aria-label', `${person.name} preference ingredient ${preferenceIndex + 1}`);
      const strength = select([[0, 'Neutral'], [1, 'Like'], [2, 'Strong like']], preference.strength,
        value => preference.strength = Number(value));
      strength.setAttribute('aria-label', `${person.name} preference strength ${preferenceIndex + 1}`);
      const remove = action('×', () => {
        person.preferences.splice(preferenceIndex, 1);
        invalidate();
        renderPeople();
      });
      remove.setAttribute('aria-label', 'Remove preference');
      row.append(ingredient, strength, remove);
      box.append(row);
    });
    box.append(action('Add ingredient preference', () => {
      if (person.preferences.length >= 20) return;
      person.preferences.push({ingredient: '', strength: 1});
      invalidate();
      renderPeople();
    }));
    box.append(
      control('Always exclude / disliked ingredients (one per line)', listInput(person.avoid, value => person.avoid = value)),
      control('Explicit allergies (one per line)', listInput(person.allergies, value => person.allergies = value)),
      action('Remove roommate', () => {
        draft.splice(index, 1);
        invalidate();
        renderPeople();
      })
    );
    $('people').append(box);
  });
}

async function post(path, data) {
  const response = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data)
  });
  let result;
  try {
    result = await response.json();
  } catch (_) {
    throw Error('The server returned an unreadable response.');
  }
  if (!response.ok) throw Error(result.message || 'Request failed.');
  return result;
}

function setBusy(value) {
  busy = value;
  for (const id of ['extract', 'manual', 'search', 'add', 'clear']) $(id).disabled = value;
  $('review').inert = value;
  $('description').disabled = value;
}

function showList(id, title, items) {
  const box = $(id);
  box.replaceChildren();
  box.hidden = !items.length;
  if (!items.length) return;
  box.append(node('strong', title));
  const list = node('ul');
  for (const item of items) list.append(node('li', item));
  box.append(list);
}

async function extractPreferences() {
  if (busy) return;
  invalidate();
  $('review').hidden = true;
  setBusy(true);
  $('notice').textContent = 'Sending your description to Gemini… Please wait.';
  try {
    const result = await post('/api/parse-preferences', {text: $('description').value});
    draft = result.roommates;
    showList('questions', 'Resolve these questions in your description or the profiles below:', result.questions);
    showList('unsupported', 'These requests are not enforced by recipe search:', result.unsupported_requests);
    renderPeople();
    $('review').hidden = false;
    $('notice').textContent = `Extracted with Gemini (${result.model}). Review before searching.`;
  } catch (error) {
    $('notice').textContent = error.message;
  } finally {
    setBusy(false);
  }
}

function emptyPerson() {
  return {name: `Roommate ${draft.length + 1}`, diet: 'Any', preferences: [], avoid: [], allergies: []};
}

function openManual() {
  invalidate();
  if (!draft.length) draft = [emptyPerson()];
  $('questions').hidden = true;
  $('unsupported').hidden = true;
  renderPeople();
  $('review').hidden = false;
  $('notice').textContent = 'Manual entry selected. No AI extraction was performed.';
}

function addPerson() {
  if (draft.length >= 12) return;
  draft.push(emptyPerson());
  invalidate();
  renderPeople();
}

function externalLink(label, url) {
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'https:') return node('span', label);
    const link = node('a', label);
    link.href = parsed.href;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    return link;
  } catch (_) {
    return node('span', label);
  }
}

function ratingControl(recipe) {
  const wrapper = node('div');
  const prior = ratings.find(rating => rating.meal_id === recipe.id && rating.household_id === householdId);
  const options = [['', 'Not rated'], [1, '1 / 5'], [2, '2 / 5'], [3, '3 / 5'], [4, '4 / 5'], [5, '5 / 5']];
  const input = select(options, prior ? prior.score : '', value => {
    ratings = ratings.filter(rating => rating.meal_id !== recipe.id || rating.household_id !== householdId);
    if (value) ratings.push({meal_id: recipe.id, score: Number(value), household_id: householdId, timestamp: new Date().toISOString()});
    ratings = ratings.slice(-500);
    save();
  }, false);
  wrapper.append(control('Rate after trying', input));
  return wrapper;
}

function card(recipe, review = false) {
  const article = node('article', undefined, 'recipe');
  article.append(node('h3', recipe.title));
  if (recipe.photo) {
    try {
      const url = new URL(recipe.photo);
      if (url.protocol === 'https:') {
        const image = node('img');
        image.src = url.href;
        image.alt = recipe.title;
        image.loading = 'lazy';
        article.append(image);
      }
    } catch (_) {
      // A bad optional image URL must not hide the recipe.
    }
  }
  article.append(node('p', recipe.happiness == null ? 'No preference score' : `Household fit: ${recipe.happiness}%`, 'score'));
  for (const reason of recipe.reasons || []) {
    article.append(node('p', `${reason.name}: ${reason.happiness == null ? 'Not scored' : reason.happiness + '% fit'} · Matched: ${(reason.matched || []).join(', ') || 'none'}`));
  }
  if (review || (recipe.review_notes || []).length) {
    article.append(node('p', (recipe.review_notes || []).join(' '), 'callout'));
  }
  const details = node('details');
  details.append(node('summary', 'Ingredients & instructions'));
  const ingredients = node('ul');
  for (const ingredient of recipe.ingredients || []) {
    ingredients.append(node('li', `${ingredient.measure} ${ingredient.name}`));
  }
  details.append(ingredients, node('p', recipe.instructions, 'instructions'), externalLink('Original recipe on TheMealDB', recipe.url));
  article.append(details);
  const bookmark = action(favorites.some(item => item.id === recipe.id) ? 'Saved' : 'Save favorite', () => {
    if (!favorites.some(item => item.id === recipe.id)) {
      favorites.push({id: recipe.id, title: recipe.title, url: recipe.url});
      save();
      renderFavorites();
    }
    bookmark.textContent = 'Saved';
  });
  article.append(bookmark, ratingControl(recipe));
  return article;
}

function renderFavorites() {
  $('favorites').replaceChildren();
  if (!favorites.length) $('favorites').append(node('p', 'Your saved meals will appear here.'));
  for (const recipe of favorites) {
    const box = node('div', undefined, 'saved');
    box.append(externalLink(recipe.title, recipe.url), ratingControl(recipe), action('Remove', () => {
      favorites = favorites.filter(item => item.id !== recipe.id);
      save();
      renderFavorites();
    }));
    $('favorites').append(box);
  }
}

async function findRecipes() {
  if (busy) return;
  if (!$('confirm').checked) {
    $('notice').textContent = 'Review the profiles and check the confirmation box before searching.';
    return;
  }
  setBusy(true);
  $('notice').textContent = 'Finding recipes that match the confirmed profiles…';
  try {
    const result = await post('/api/recommend', {roommates: draft, household_id: householdId, ratings});
    confirmed = structuredClone(draft);
    save();
    $('cards').replaceChildren(...result.recipes.map(recipe => card(recipe)));
    $('review-cards').replaceChildren(...result.review_recipes.map(recipe => card(recipe, true)));
    $('review-heading').hidden = !result.review_recipes.length;
    $('results').hidden = false;
    $('result-note').textContent = result.message || `${result.recipes.length} meal ideas · ${result.excluded_by_rules} excluded by screening.`;
    $('notice').textContent = 'Recipe search complete.';
    $('results').scrollIntoView({behavior: 'smooth'});
  } catch (error) {
    $('notice').textContent = error.message;
  } finally {
    setBusy(false);
  }
}

function clearData() {
  if (!window.confirm('Clear confirmed profiles, bookmarks, and ratings saved by this version of RMR?')) return;
  confirmed = [];
  draft = [];
  favorites = [];
  ratings = [];
  householdId = crypto.randomUUID();
  try { localStorage.removeItem(KEY); } catch (_) {}
  $('review').hidden = true;
  $('results').hidden = true;
  $('description').value = '';
  $('notice').textContent = 'Saved data cleared.';
  renderFavorites();
}

// This reads local settings only; it does not spend a Gemini request.
async function checkSetup(manual = false) {
  const button = $('check-setup');
  const message = $('ai-status');
  if (button.disabled) return;
  button.disabled = true;
  button.textContent = 'Checking…';
  message.textContent = 'Checking local Gemini configuration…';
  message.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch('/api/ai-status', {cache: 'no-store'});
    if (!response.ok) throw Error('Setup status unavailable.');
    const status = await response.json();
    const checkedAt = new Date().toLocaleTimeString();
    message.textContent = `Local check completed at ${checkedAt}. Gemini (${status.model}): ${status.message}`;
  } catch (_) {
    message.textContent = 'Setup check failed. Confirm that the RMR server is running, then try again.';
  } finally {
    button.disabled = false;
    button.textContent = 'Check setup';
    message.setAttribute('aria-busy', 'false');
    if (manual) message.scrollIntoView({behavior: 'smooth', block: 'nearest'});
  }
}

$('description').addEventListener('input', invalidate);
$('extract').addEventListener('click', extractPreferences);
$('manual').addEventListener('click', openManual);
$('add').addEventListener('click', addPerson);
$('search').addEventListener('click', findRecipes);
$('clear').addEventListener('click', clearData);
$('check-setup').addEventListener('click', () => checkSetup(true));
if (confirmed.length) {
  draft = structuredClone(confirmed);
  renderPeople();
  $('review').hidden = false;
}
renderFavorites();
checkSetup();
