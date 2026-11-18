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
  field.querySelector(".remove").onclick = () => {
    field.remove(); numberProfiles(); invalidate(); saveHousehold(); $("add").focus();
  };
  numberProfiles();
  if (focus) { invalidate(); saveHousehold(); field.querySelector(".name").focus(); }
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
function render() {
  cards.replaceChildren();
  const list = chosen ? [chosen] : recipes;
  $("status").textContent = chosen ? "Your household chose " + chosen.title + "." :
    list.length ? list.length + (list.length === 1 ? " recipe matches" : " recipes match") + " your household. Best match first." :
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
    const reasons=node("ul",undefined,"reasons");
    for(const p of r.reasons) {
      let why=p.total ? (p.matched.length ? "likes " + p.matched.join(", ") : "no listed likes matched") : "no likes specified";
      if(p.diet!=="Any") why+=" · fits "+p.diet.toLowerCase()+" filter";
      reasons.append(node("li",p.name+" — "+why));
    }
    body.append(reasons);
    for (const note of r.review_notes || []) body.append(node("p", note, "review-note"));
    const details=node("details"); details.open=Boolean(chosen);
    details.append(node("summary","Ingredients & instructions"));
    const ingredients=node("ul");
    r.ingredients.forEach(item=>ingredients.append(node("li",[item.measure,item.name].filter(Boolean).join(" "))));
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
    body.append(details,actions);card.append(body);(flagged ? $("review-cards") : cards).append(card);
  }
}
let hasResultsScreen = false;
function showScreen(results) {
  $("entry").hidden = results;
  $("results").hidden = !results;
  document.title = results ? "Recipe matches · RMR" : "RMR · Roommate Meal Resolutions";
  window.scrollTo(0, 0);
  if (results) $("results-title").focus();
  else people.querySelector(".name").focus();
}
function syncScreen() {
  if (location.hash === "#results" && !hasResultsScreen)
    history.replaceState(null, "", location.pathname + location.search);
  showScreen(location.hash === "#results");
}
window.addEventListener("popstate", syncScreen);
$("edit").onclick = () => history.back();
house.oninput = () => { invalidate(); saveHousehold(); };
$("add").onclick=()=>addPerson(true);
house.onsubmit=async event=>{
  event.preventDefault();
  invalidate(); const token=generation;
  controller=new AbortController();
  const request = householdForm();
  const roommates = request.roommates;
  $("find").disabled=true; $("status").textContent="Searching TheMealDB and comparing ingredients…";
  $("screen-note").hidden = !roommates.some(p => p.allergies.length || p.diet === "Gluten Free");
  hasResultsScreen = true;
  history.pushState(null, "", "#results");
  showScreen(true);
  try {
    const res=await fetch("/api/recommend",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify(request),signal:controller.signal});
    const data=await res.json();
    if(token!==generation)return;
    if(!res.ok || !(data.recipes?.length || data.review_recipes?.length)) {$("status").textContent=data.message;return;}
    recipes=data.recipes;reviewRecipes=data.review_recipes || [];render();
  } catch(err) {
    if(token===generation) $("status").textContent="Could not reach RMR. Check that the Python window is still open and try again.";
  } finally { if(token===generation) $("find").disabled=false; }
};
// Keep these original keys so existing RMR households and bookmarks load after the rename.
const HOUSE_KEY = "shared-table.household.v1";
const FAV_KEY = "shared-table.favorites.v1";
const fields = ["name", "diet", "likes", "avoid", "allergies"];
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
  const roommates = [...people.children].map(field => Object.fromEntries(
    fields.map(k => [k, field.querySelector("."+k).value])));
  return {roommates};
}
function householdForm() {
  const data = draft();
  for (const person of data.roommates) {
    for (const field of ["likes","avoid","allergies"]) person[field] = split(person[field]);
  }
  return data;
}
function saveHousehold() { writeSave(HOUSE_KEY, draft()); }
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
