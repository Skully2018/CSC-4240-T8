"use strict";
const $ = id => document.getElementById(id);
const house = $("house"), people = $("people"), cards = $("cards");
let recipes = [], reviewRecipes = [], chosen = null, generation = 0, controller;
const split = value => value.split(",").map(s => s.trim()).filter(Boolean);

function invalidate() {
  hasResultsScreen = false;
  generation++;
  if (controller) controller.abort();
  recipes = []; reviewRecipes = []; chosen = null;
  $("review-cards").replaceChildren(); $("review-section").hidden = true;
  cards.replaceChildren();
  $("find").disabled = false;
  $("status").textContent = "Choose Find recipes to search with these preferences.";
}
function addPerson(focus) {
  const field = $("profile").content.firstElementChild.cloneNode(true);
  people.append(field);
  field.querySelector(".add-preference").onclick = () => addPreference(field);
  field.querySelector(".remove").onclick = () => {
    field.remove(); numberProfiles(); invalidate(); saveHousehold(); $("add").focus();
  };
  numberProfiles();
  addPreference(field);
  if (focus) { invalidate(); saveHousehold(); field.querySelector(".name").focus(); }
}
function addPreference(field, ingredient = "", strength = 1) {
  const row = node("div", undefined, "preference-row");
  const input = node("input"); input.type="text"; input.maxLength=80;
  input.placeholder="Ingredient, e.g. mushrooms"; input.value=ingredient;
  input.setAttribute("aria-label","Ingredient preference");
  const select=node("select"); select.setAttribute("aria-label","Preference strength");
  for (const [value,label] of [[0,"Neutral"],[1,"Like"],[2,"Strong like"]]) {
    const option=node("option",label); option.value=value; option.selected=Number(strength)===value; select.append(option);
  }
  const remove=action("Remove",()=>{row.remove();saveHousehold();invalidate();});
  remove.className="remove-preference";
  row.append(input,select,remove); field.querySelector(".preferences").append(row);
}
function numberProfiles() {
  [...people.children].forEach((field,i) => {
    field.querySelector("legend").textContent = "Roommate " + (i+1);
    field.querySelector(".remove").hidden = people.children.length === 1;
  });
  $("add").disabled = people.children.length >= 12;
}
function node(tag, text, cls) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (cls) el.className = cls;
  return el;
}
function action(label, fn, cls) {
  const btn = node("button",label,cls); btn.type="button"; btn.onclick=fn; return btn;
}
function happinessBadge(value) {
  if (value === null || value === undefined) return node("strong","Not scored","happiness-score score-neutral");
  const score=Math.round(Number(value)||0);
  const level=score<35?"low":score<=60?"medium":"high";
  return node("strong",score+"%","happiness-score score-"+level);
}
function normalizeRecipe(recipe) {
  if (!recipe) return null;

  const r = { ...recipe };

  // Convert Agent 2's roommate scores into the
  // format expected by the existing recipe cards.
  if (!Array.isArray(r.reasons)) {
    const scores = r.roommate_scores || [];

    r.reasons = scores.map(p => ({
      name: p.name || "Roommate",
      matched: p.matched || [],
      total: p.total || 0,
      happiness: p.happiness ?? p.score ?? null,
      diet: p.diet || "Any"
    }));
  }

  // Ensure the recipe contains fields render() expects.
  r.ingredients = Array.isArray(r.ingredients)
    ? r.ingredients
    : [];

  r.review_notes = Array.isArray(r.review_notes)
    ? r.review_notes
    : [];

  r.happiness = r.happiness == null ? null : Number(r.happiness);
  r.instructions = r.instructions || "";
  r.title = r.title || "Untitled recipe";

  return r;
}
function render() {
  cards.replaceChildren();
  const list = chosen ? [chosen] : recipes;
  $("status").textContent = chosen ? "Your household chose " + chosen.title + "." :
    list.length && list.every(r=>r.happiness==null) ? "Household happiness cannot be scored yet. Add a like or strong like for at least one roommate." :
    list.length && list.every(r=>r.happiness===0) ? "No recipe has a positive household taste score. Add ingredients your roommates like or adjust preference strengths to improve the ranking." :
    list.length ? list.length + (list.length === 1 ? " recipe ranked" : " recipes ranked") + " by household taste fit. Best match first." :
    "You’ve skipped every match. Adjust your preferences or start a new search.";
  if (!chosen && !recipes.length && reviewRecipes.length)
    $("status").textContent = "Review the flagged ingredients in the recipes below.";
  $("review-cards").replaceChildren();
  $("review-section").hidden = !!chosen || !reviewRecipes.length;
  for (const r of chosen ? list : [...list, ...reviewRecipes]) {
    const flagged = !!r.review_notes?.length;
    const card = node("article",undefined,"card");
    if (r.photo && r.photo.startsWith("https://")) {
      const img = node("img"); img.alt=""; img.loading="lazy"; img.src=r.photo;
      img.onerror=()=>img.remove(); card.append(img);
    }
    const body=node("div",undefined,"content");
    body.append(node("div",[r.area,r.category].filter(Boolean).join(" · "),"meta"),node("h3",r.title));
    const householdScore=node("p",undefined,"happiness");
    householdScore.append(node("span","Household happiness: "),happinessBadge(r.happiness),
      node("span",r.happiness==null?" (no preferences to score)":" household fit"));
    body.append(householdScore);
    const reasons=node("ul",undefined,"reasons");
    for(const p of (r.reasons || [])) {
      let why=p.total ? (p.matched.length ? "matched " + p.matched.join(", ") : "no listed preferences matched") : "no preferences specified";
      if(p.diet!=="Any") why+=" · fits "+p.diet.toLowerCase()+" filter";
      const reason=node("li");
      reason.append(document.createTextNode(p.name+" — "+why+" · "),happinessBadge(p.happiness),document.createTextNode(" happiness"));
      reasons.append(reason);
    }
    body.append(reasons);
    for (const note of r.review_notes || []) body.append(node("p", note, "review-note"));
    const details=node("details"); details.open=Boolean(chosen);
    details.append(node("summary","Ingredients & instructions"));
    const ingredients=node("ul");
    (r.ingredients || []).forEach(item => {
      ingredients.append(
        node("li", [item.measure, item.name].filter(Boolean).join(" "))
      );
    });
    const link=node("a","View on TheMealDB"); link.href=r.url; link.target="_blank"; link.rel="noopener";
    details.append(ingredients,node("p",r.instructions,"instructions"),link);
    const actions=node("div",undefined,"actions");
    if(chosen) actions.append(action("Back to matches",()=>{chosen=null;render();}));
    else {
      if (!flagged) actions.append(action("Choose this recipe",()=>{chosen=r; render();},"primary"));
      actions.append(action("Skip",()=>{
        recipes=recipes.filter(x=>x.id!==r.id);
        reviewRecipes=reviewRecipes.filter(x=>x.id!==r.id);
        render();
      }));
    }
    actions.append(action(favorites.some(f=>f.id===r.id) ? "Remove favorite" : "Save favorite",
      ()=>toggleFavorite(r)));
    const ratingRow=node("div",undefined,"rating-row");
    const savedRating=getRating(r.id);
    const ratingSelect=node("select"); ratingSelect.setAttribute("aria-label","Rate this recipe from 1 to 5 stars");
    const emptyRating=node("option","Rate this recipe"); emptyRating.value=""; ratingSelect.append(emptyRating);
    for(let value=1;value<=5;value++){
      const option=node("option","★".repeat(value)+" ("+value+")");
      option.value=value; option.selected=Number(savedRating?.score)===value; ratingSelect.append(option);
    }
    ratingRow.append(ratingSelect,action(savedRating?"Update rating":"Save rating",()=>{
      if(ratingSelect.value)saveRating(r.id,Number(ratingSelect.value));
    }));
    if(savedRating){ratingRow.append(action("Remove rating",()=>removeRating(r.id)),node("span","Household rating: "+savedRating.score+"/5"));}
    body.append(ratingRow);
    body.append(details,actions);card.append(body);(flagged ? $("review-cards") : cards).append(card);
  }
}
let hasResultsScreen = false;
function showScreen(screen) {
  $("entry").hidden=screen!=="entry";
  $("results").hidden=screen!=="results";
  $("happiness-page").hidden=screen!=="happiness";
  document.title=screen==="results"?"Recipe matches · RMR":screen==="happiness"?"How recommendations work · RMR":"RMR · Roommate Meal Resolutions";
  window.scrollTo(0, 0);
  if(screen==="results")$("results-title").focus();
  else if(screen==="happiness")$("happiness-title").focus();
  else people.querySelector(".name").focus();
}
function syncScreen() {
  if (location.hash === "#results" && !hasResultsScreen)
    history.replaceState(null, "", location.pathname + location.search);
  showScreen(location.hash==="#happiness"?"happiness":location.hash==="#results"&&hasResultsScreen?"results":"entry");
}
window.addEventListener("popstate", syncScreen);
window.addEventListener("hashchange",syncScreen);
document.querySelectorAll(".how-link").forEach(button=>{
  button.onclick=()=>{history.pushState(null,"","#happiness");syncScreen();};
});
$("happiness-back").onclick=()=>history.back();
$("edit").onclick = () => history.back();
house.oninput = () => { invalidate(); saveHousehold(); };
house.onchange = () => { invalidate(); saveHousehold(); };
$("add").onclick=()=>addPerson(true);
house.onsubmit = async event => {
  event.preventDefault();

  invalidate();
  const token = generation;

  controller = new AbortController();

  const request = householdForm();
  request.household_id = householdId();
  request.ratings = loadRatings();

  const roommates = request.roommates;

  $("find").disabled = true;
  $("status").textContent =
    "Searching TheMealDB and comparing ingredients…";

  $("screen-note").hidden = !roommates.some(
    p => p.allergies.length || p.diet === "Gluten Free"
  );

  hasResultsScreen = true;
  history.pushState(null, "", "#results");
  showScreen("results");

  try {
    // Send the household data to Agent 1, which applies the household happiness formula.
    const res = await fetch("/api/recommend", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(request),
      signal: controller.signal
    });

    // Read Agent 1's ranked recipe results
    const data = await res.json();

    console.log("Agent 1 response:", data);

    // Ignore outdated requests
    if (token !== generation) return;

    // Handle server errors
    if (!res.ok) {
      $("status").textContent =
        data.message || `Request failed (${res.status}).`;
      return;
    }

    // Agent 2 returns one recipe.
    // Agent 1 returns an array of recipes.
    const accepted = Array.isArray(data.recipes)
      ? data.recipes
      : data.recipe
        ? [data.recipe]
        : [];

    // Normalize recipe data for the existing UI
    recipes = accepted
      .map(normalizeRecipe)
      .filter(Boolean);

    reviewRecipes = (data.review_recipes || [])
      .map(normalizeRecipe)
      .filter(Boolean);

    // Handle no matching recipes
    if (!recipes.length && !reviewRecipes.length) {
      $("status").textContent =
        data.message || "No verified recipe found.";
      return;
    }

    // Display the accepted recipes
    render();

  } catch (err) {
    // Ignore requests canceled by changing preferences
    if (err.name === "AbortError") return;

    console.error(
      "Recipe request or rendering failed:",
      err
    );

    if (token === generation) {
      $("status").textContent =
        "Could not display recipe. Check the browser Console (F12) for details.";
    }

  } finally {
    if (token === generation) {
      $("find").disabled = false;
    }
  }
};
// Keep these original keys so existing RMR households and bookmarks load after the rename.
const HOUSE_KEY = "shared-table.household.v1";
const FAV_KEY = "shared-table.favorites.v1";
const HOUSEHOLD_ID_KEY = "rmr.household-id.v1";
const RATINGS_KEY = "rmr.recipe-ratings.v1";
const fields = ["name", "diet", "avoid", "allergies"];
function readSave(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; }
  catch { $("save-status").textContent = "Saved data could not be loaded in this browser."; return fallback; }
}
function writeSave(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    $("save-status").textContent = "Saved in this browser.";
    return true;
  } catch {
    $("save-status").textContent = "Could not save changes. Check browser storage settings or free some space.";
    return false;
  }
}
function draft() {
  const roommates=[...people.children].map(field=>({
    ...Object.fromEntries(fields.map(k=>[k,field.querySelector("."+k).value])),
    preferences:[...field.querySelectorAll(".preference-row")].map(row=>({
      ingredient:row.querySelector("input").value.trim(),
      strength:Number(row.querySelector("select").value),
    })).filter(p=>p.ingredient),
  }));
  return {roommates};
}
function householdForm() {
  const data = draft();
  for (const person of data.roommates) {
    for (const field of ["avoid","allergies"]) person[field] = split(person[field]);
  }
  return data;
}
function saveHousehold() { writeSave(HOUSE_KEY, draft()); }
function householdId(){
  let id=localStorage.getItem(HOUSEHOLD_ID_KEY);
  if(!id){id=globalThis.crypto?.randomUUID?.()||"rmr-"+Date.now().toString(36)+Math.random().toString(36).slice(2);localStorage.setItem(HOUSEHOLD_ID_KEY,id);}
  return id;
}
function loadRatings(){
  try{
    const id=householdId(),rows=JSON.parse(localStorage.getItem(RATINGS_KEY)||"[]");
    return Array.isArray(rows)?rows.filter(r=>r?.household_id===id&&/^\d+$/.test(r.meal_id)&&Number.isInteger(r.score)&&r.score>=1&&r.score<=5):[];
  }catch{return [];}
}
function getRating(mealId){return loadRatings().find(r=>r.meal_id===mealId);}
function saveRating(mealId,score){
  const id=householdId(),rows=loadRatings().filter(r=>r.meal_id!==mealId);
  rows.push({household_id:id,meal_id:mealId,score,timestamp:new Date().toISOString()});
  if(writeSave(RATINGS_KEY,rows))house.requestSubmit();
}
function removeRating(mealId){
  const rows=loadRatings().filter(r=>r.meal_id!==mealId);
  if(writeSave(RATINGS_KEY,rows))house.requestSubmit();
}
function loadHousehold() {
  const data = readSave(HOUSE_KEY, null);
  if (!Array.isArray(data?.roommates) || !data.roommates.length) {
    addPerson(false); addPerson(false); return;
  }
  for (const profile of data.roommates.slice(0,12)) {
    addPerson(false);
    for (const k of fields) {
      if (typeof profile?.[k] === "string") people.lastElementChild.querySelector("."+k).value = profile[k];
    }
    if(Array.isArray(profile?.preferences)){
      people.lastElementChild.querySelector(".preferences").replaceChildren();
      for(const pref of profile.preferences){
        if(typeof pref?.ingredient==="string")addPreference(people.lastElementChild,pref.ingredient,[0,1,2].includes(pref.strength)?pref.strength:pref.strength<0?0:1);
      }
    }else if(typeof profile?.likes==="string"){
      people.lastElementChild.querySelector(".preferences").replaceChildren();
      split(profile.likes).forEach(ingredient=>addPreference(people.lastElementChild,ingredient,1));
    }
    if (profile?.allergies) people.lastElementChild.querySelector(".allergy").open = true;
  }
}
function loadFavorites() {
  const saved = readSave(FAV_KEY, []);
  return Array.isArray(saved) ? saved.filter(r => /^\d+$/.test(r?.id) && typeof r.title === "string") : [];
}
let favorites = loadFavorites();
function toggleFavorite(recipe) {
  const current = loadFavorites();
  const removing = current.some(r=>r.id===recipe.id);
  const next = removing ? current.filter(r=>r.id!==recipe.id) : [...current,{id:recipe.id,title:recipe.title}];
  if (writeSave(FAV_KEY, next)) {
    favorites = next;
    renderBookmarks();
    if (!$("results").hidden) render();
  }
}
function renderBookmarks() {
  const list = $("bookmarks");
  list.replaceChildren();
  if (!favorites.length) list.append(node("p","Recipes you save will appear here."));
  for (const r of favorites) {
    const row = node("div",undefined,"bookmark");
    const link = node("a",r.title);
    link.href = "https://www.themealdb.com/meal/" + r.id;
    link.target = "_blank"; link.rel = "noopener";
    row.append(link,action("Remove",()=>toggleFavorite(r))); list.append(row);
  }
}
window.addEventListener("storage", e=>{
  if (e.key===FAV_KEY || e.key===null) {
    favorites=loadFavorites(); renderBookmarks();
    if (!$("results").hidden && (recipes.length || reviewRecipes.length)) render();
  }
});
loadHousehold();
renderBookmarks();
syncScreen();
