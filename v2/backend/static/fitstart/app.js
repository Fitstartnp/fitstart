(() => {
  "use strict";

  const state = { account: null, profile: null, households: [], weights: [], measures: [], foods: [], waters: [], meals: [], groceries: [], groceryItems: {}, workouts: [], workoutSets: {}, fastings: [], goals: [], catalogRecipes: [], favoriteRecipeIds: new Set(), catalogRoutines: [] };
  const $ = (id) => document.getElementById(id);

  function cookie(name) {
    const prefix = name + "=";
    const item = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith(prefix));
    return item ? decodeURIComponent(item.slice(prefix.length)) : "";
  }

  async function api(path, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const headers = { Accept: "application/json", ...(options.headers || {}) };
    const init = { method, credentials: "same-origin", headers };
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(options.body);
    }
    if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
      headers["X-CSRFToken"] = cookie("csrftoken");
    }
    const response = await fetch("/api/v1" + path, init);
    const type = response.headers.get("content-type") || "";
    const result = type.includes("application/json") ? await response.json() : null;
    if (!response.ok) {
      const detail = result?.detail || Object.entries(result || {}).map(([key, value]) =>
        key + ": " + (Array.isArray(value) ? value.join(" ") : String(value))
      ).join(" · ");
      throw new Error(detail || "Request failed (" + response.status + ").");
    }
    return result;
  }

  function setDateDefaults() {
    const now = new Date();
    const today = [
      now.getFullYear(),
      String(now.getMonth() + 1).padStart(2, "0"),
      String(now.getDate()).padStart(2, "0")
    ].join("-");
    if ($("planDate") && !$("planDate").value) $("planDate").value = today;
    if ($("groceryWeek") && !$("groceryWeek").value) $("groceryWeek").value = today;
  }

  function showStatus(id, message, kind = "") {
    const node = $(id);
    if (!node) return;
    node.textContent = message;
    node.className = "status" + (kind ? " " + kind : "");
  }

  function addCell(row, value) {
    const cell = document.createElement("td");
    cell.textContent = value === null || value === undefined || value === "" ? "—" : String(value);
    row.appendChild(cell);
  }

  function renderTable(id, columns, rows, emptyText) {
    const host = $(id);
    host.replaceChildren();
    if (!rows.length) {
      const p = document.createElement("p");
      p.className = "empty";
      p.textContent = emptyText;
      host.appendChild(p);
      return;
    }
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const head = document.createElement("tr");
    columns.forEach((column) => addCell(head, column.label));
    thead.appendChild(head);
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    rows.forEach((item) => {
      const tr = document.createElement("tr");
      columns.forEach((column) => addCell(tr, column.value(item)));
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    host.appendChild(wrap);
  }

  function renderHouseholds() {
    const host = $("householdList");
    host.replaceChildren();
    if (!state.households.length) {
      const p = document.createElement("p");
      p.className = "empty";
      p.textContent = "No household yet. Create one to invite another person.";
      host.appendChild(p);
    }
    state.households.forEach((item) => {
      const row = document.createElement("div");
      row.className = "household";
      const name = document.createElement("strong");
      name.textContent = item.name;
      const role = document.createElement("span");
      role.className = "pill";
      role.textContent = item.role;
      row.append(name, role);
      host.appendChild(row);
    });

    ["inviteHousehold", "weightHousehold", "measureHousehold", "foodHousehold", "waterHousehold", "mealHousehold", "groceryHousehold", "workoutHousehold", "fastingHousehold", "goalHousehold"].forEach((id) => {
      const select = $(id);
      const previous = select.value;
      select.replaceChildren();
      if (id !== "inviteHousehold") {
        const privateOption = document.createElement("option");
        privateOption.value = "";
        privateOption.textContent = "Private to me";
        select.appendChild(privateOption);
      }
      state.households.forEach((item) => {
        const option = document.createElement("option");
        option.value = String(item.id);
        option.textContent = item.name + " (" + item.role + ")";
        select.appendChild(option);
      });
      if (state.households.some((item) => String(item.id) === previous)) select.value = previous;
    });
    $("inviteButton").disabled = state.households.length === 0;
  }

  function renderProfile() {
    const profile = state.profile;
    $("displayName").value = profile.display_name || "";
    $("unitSystem").value = profile.unit_system;
    $("timezoneName").value = profile.timezone_name;
    $("profileAge").value = profile.age;
    $("profileGender").value = profile.gender;
    $("profileHeight").value = profile.height_cm;
    $("profileStartWeight").value = profile.start_weight_kg;
    $("profileCurrentWeight").value = profile.current_weight_kg;
    $("profileGoalWeight").value = profile.goal_weight_kg;
    $("profileActivity").value = profile.activity_multiplier;
    $("profileDeficit").value = profile.daily_deficit_kcal;
    $("profileDiet").value = profile.diet_type;
    $("profileWorkoutMode").value = profile.workout_mode;
    $("profileFitnessLevel").value = profile.fitness_level;
    const mapping = {
      share_weight_history: "shareWeightHistory",
      share_body_measurements: "shareBodyMeasurements",
      share_food_diary: "shareFoodDiary",
      share_water_logs: "shareWaterLogs",
      share_meal_plans: "shareMealPlans",
      share_grocery_lists: "shareGroceryLists",
      share_workout_history: "shareWorkoutHistory",
      share_workout_plans: "shareWorkoutPlans",
      share_fasting_sessions: "shareFastingSessions",
      share_goals: "shareGoals"
    };
    Object.entries(mapping).forEach(([key, id]) => {
      $(id).checked = Boolean(profile.sharing?.[key.replace("share_", "")]);
    });
  }

  function renderChildSelectors() {
    const lists = $("groceryParentList");
    const sessions = $("workoutParentSession");
    [[lists, state.groceries], [sessions, state.workouts]].forEach(([select, records]) => {
      if (!select) return;
      const previous = select.value;
      select.replaceChildren();
      records.filter((record) => record.owner === state.account.id).forEach((record) => {
        const option = document.createElement("option");
        option.value = String(record.id);
        option.textContent = record.name || record.title || ("Record " + record.id);
        select.appendChild(option);
      });
      if ([...select.options].some((option) => option.value === previous)) select.value = previous;
    });
    if (lists) $("groceryItemButton").disabled = lists.options.length === 0;
    if (sessions) $("workoutSetButton").disabled = sessions.options.length === 0;
  }

  async function loadChildRecords() {
    const groceryPairs = await Promise.all(state.groceries.map(async (list) => [
      list.id,
      await api("/grocery-lists/" + list.id + "/items/")
    ]));
    const workoutPairs = await Promise.all(state.workouts.map(async (session) => [
      session.id,
      await api("/workout-sessions/" + session.id + "/sets/")
    ]));
    state.groceryItems = Object.fromEntries(groceryPairs);
    state.workoutSets = Object.fromEntries(workoutPairs);
  }

  function renderGroceryItems() {
    const host = $("groceryItemTable");
    host.replaceChildren();
    const lists = state.groceries;
    const rows = lists.flatMap((list) => (state.groceryItems[list.id] || []).map((item) => ({ ...item, list })));
    if (!rows.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "No items yet. Choose a list above to add its first item.";
      host.appendChild(empty);
      return;
    }
    const table = document.createElement("table");
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    ["Done", "Item", "Quantity", "Category", "List"].forEach((text) => addCell(headRow, text));
    head.appendChild(headRow);
    table.appendChild(head);
    const body = document.createElement("tbody");
    rows.forEach((item) => {
      const row = document.createElement("tr");
      const statusCell = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = item.is_checked;
      checkbox.disabled = item.list.owner !== state.account.id;
      checkbox.setAttribute("aria-label", "Mark " + item.name + " as purchased");
      checkbox.addEventListener("change", async () => {
        checkbox.disabled = true;
        try {
          await api("/grocery-lists/" + item.grocery_list + "/items/" + item.id + "/", {
            method: "PATCH", body: { is_checked: checkbox.checked }
          });
          await refreshRecords();
        } catch (error) {
          checkbox.checked = !checkbox.checked;
          showStatus("groceryItemStatus", error.message, "error");
        } finally {
          checkbox.disabled = item.list.owner !== state.account.id;
        }
      });
      statusCell.appendChild(checkbox);
      row.appendChild(statusCell);
      addCell(row, item.name);
      addCell(row, item.quantity);
      addCell(row, item.category);
      addCell(row, item.list.name);
      body.appendChild(row);
    });
    table.appendChild(body);
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    wrap.appendChild(table);
    host.appendChild(wrap);
  }

  function renderWorkoutSets() {
    const host = $("workoutSetTable");
    host.replaceChildren();
    const rows = state.workouts.flatMap((session) => (state.workoutSets[session.id] || []).map((set) => ({ ...set, sessionRecord: session })));
    if (!rows.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "No exercise sets logged yet.";
      host.appendChild(empty);
      return;
    }
    const table = document.createElement("table");
    const head = document.createElement("thead");
    const header = document.createElement("tr");
    ["Workout", "Exercise", "Set", "Reps", "Load", "Duration"].forEach((text) => addCell(header, text));
    head.appendChild(header);
    table.appendChild(head);
    const body = document.createElement("tbody");
    rows.forEach((item) => {
      const row = document.createElement("tr");
      addCell(row, item.sessionRecord.title);
      addCell(row, item.exercise_name);
      addCell(row, item.set_number);
      addCell(row, item.reps);
      addCell(row, item.weight_kg == null ? "—" : item.weight_kg + " kg");
      addCell(row, item.duration_seconds == null ? "—" : item.duration_seconds + " sec");
      body.appendChild(row);
    });
    table.appendChild(body);
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    wrap.appendChild(table);
    host.appendChild(wrap);
  }

  function renderTimedSessions(hostId, records, kind) {
    const host = $(hostId);
    host.replaceChildren();
    if (!records.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = kind === "workout" ? "No workout sessions yet." : "No fasting sessions yet.";
      host.appendChild(empty);
      return;
    }
    const table = document.createElement("table");
    const header = document.createElement("thead");
    const headerRow = document.createElement("tr");
    const labels = kind === "workout" ? ["Started", "Workout", "Notes", "Action"] : ["Started", "Target", "Ended", "Action"];
    labels.forEach((label) => addCell(headerRow, label));
    header.appendChild(headerRow);
    table.appendChild(header);
    const body = document.createElement("tbody");
    records.forEach((record) => {
      const row = document.createElement("tr");
      addCell(row, new Date(record.started_at).toLocaleString());
      if (kind === "workout") {
        addCell(row, record.title);
        addCell(row, record.notes);
      } else {
        addCell(row, record.target_hours + " h");
        addCell(row, record.ended_at ? new Date(record.ended_at).toLocaleString() : "In progress");
      }
      const action = document.createElement("td");
      if (!record.ended_at && record.owner === state.account.id) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn small secondary";
        button.textContent = kind === "workout" ? "Finish workout" : "End fast";
        button.addEventListener("click", async () => {
          button.disabled = true;
          try {
            const path = kind === "workout" ? "/workout-sessions/" : "/fasting-sessions/";
            await api(path + record.id + "/", {
              method: "PATCH",
              body: { ended_at: new Date().toISOString() }
            });
            await refreshRecords();
          } catch (error) {
            button.disabled = false;
            showStatus(kind === "workout" ? "workoutStatus" : "fastingStatus", error.message, "error");
          }
        });
        action.appendChild(button);
      } else {
        action.textContent = record.ended_at ? "Completed" : "Read only";
      }
      row.appendChild(action);
      body.appendChild(row);
    });
    table.appendChild(body);
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    wrap.appendChild(table);
    host.appendChild(wrap);
  }

  function renderAll() {
    $("accountEmail").textContent = state.account.email;
    $("weightCount").textContent = String(state.weights.length);
    $("foodCount").textContent = String(state.foods.length);
    $("workoutCount").textContent = String(state.workouts.length);
    $("goalCount").textContent = String(state.goals.length);
    renderProfile();
    renderHouseholds();
    renderChildSelectors();
    renderGroceryItems();
    renderWorkoutSets();
    renderTable("weightTable", [
      { label: "Date", value: (r) => r.measured_on },
      { label: "Weight", value: (r) => r.weight_kg + " kg" },
      { label: "Note", value: (r) => r.note }
    ], state.weights, "No weight entries yet.");
    renderTable("measureTable", [
      { label: "Measured", value: (r) => new Date(r.measured_at).toLocaleString() },
      { label: "Waist", value: (r) => r.waist_cm == null ? "—" : r.waist_cm + " cm" },
      { label: "Hips", value: (r) => r.hip_cm == null ? "—" : r.hip_cm + " cm" },
      { label: "Chest", value: (r) => r.chest_cm == null ? "—" : r.chest_cm + " cm" }
    ], state.measures, "No body measurements yet.");
    renderTable("foodTable", [
      { label: "Logged", value: (r) => new Date(r.logged_at).toLocaleString() },
      { label: "Food", value: (r) => r.food_name },
      { label: "Meal", value: (r) => r.meal_slot },
      { label: "Energy", value: (r) => r.calories_kcal == null ? "—" : r.calories_kcal + " kcal" }
    ], state.foods, "No food entries yet.");
    renderTable("waterTable", [
      { label: "Logged", value: (r) => new Date(r.logged_at).toLocaleString() },
      { label: "Amount", value: (r) => r.amount_ml + " ml" }
    ], state.waters, "No water entries yet.");
    renderTable("mealTable", [
      { label: "Date", value: (r) => r.plan_date },
      { label: "Meal", value: (r) => r.meal_slot },
      { label: "Plan", value: (r) => r.title },
      { label: "Servings", value: (r) => r.servings }
    ], state.meals, "No planned meals yet.");
    renderTable("groceryTable", [
      { label: "Week of", value: (r) => r.week_of },
      { label: "List", value: (r) => r.name },
      { label: "Status", value: (r) => r.is_archived ? "Archived" : "Active" }
    ], state.groceries, "No grocery lists yet.");
    renderTimedSessions("workoutTable", state.workouts, "workout");
    renderTimedSessions("fastingTable", state.fastings, "fasting");
    renderTable("goalTable", [
      { label: "Goal", value: (r) => r.title },
      { label: "Metric", value: (r) => r.metric_key },
      { label: "Target", value: (r) => r.target_value + (r.unit ? " " + r.unit : "") },
      { label: "Status", value: (r) => r.status }
    ], state.goals, "No goals yet.");
  }

  function renderRecipeCatalog() {
    const host = $("recipeResults");
    if (!host) return;
    host.replaceChildren();
    if (!state.catalogRecipes.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "No recipes matched these filters.";
      host.appendChild(empty);
      return;
    }
    const grid = document.createElement("div");
    grid.className = "catalog-grid";
    state.catalogRecipes.forEach((recipe) => {
      const card = document.createElement("article");
      card.className = "catalog-card";
      const header = document.createElement("div");
      header.className = "catalog-card-header";
      const title = document.createElement("h3");
      title.textContent = (recipe.icon || "🍽️") + " " + recipe.name;
      const subtitle = document.createElement("p");
      subtitle.className = "muted";
      subtitle.textContent = recipe.diet_style.replaceAll("_", " ") + " · " + recipe.slot + " · Menu " + recipe.menu_number;
      header.append(title, subtitle);
      card.appendChild(header);

      const macros = document.createElement("p");
      macros.className = "catalog-meta";
      macros.textContent = recipe.base_calories_kcal + " kcal · Protein " + recipe.base_macros.p + "g · Carbs " + recipe.base_macros.c + "g · Fat " + recipe.base_macros.f + "g";
      card.appendChild(macros);

      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = "Ingredients & cooking instructions";
      details.appendChild(summary);
      const ingredients = document.createElement("ul");
      recipe.portions.forEach((portion) => {
        const li = document.createElement("li");
        li.textContent = portion.qty + " " + portion.unit + " " + portion.item;
        ingredients.appendChild(li);
      });
      details.appendChild(ingredients);
      const steps = document.createElement("ol");
      recipe.steps.forEach((step) => {
        const li = document.createElement("li");
        li.textContent = step;
        steps.appendChild(li);
      });
      details.appendChild(steps);
      const tip = document.createElement("p");
      tip.className = "muted";
      tip.textContent = recipe.tip;
      details.appendChild(tip);
      card.appendChild(details);

      const actions = document.createElement("div");
      actions.className = "catalog-actions";
      const favorite = document.createElement("button");
      favorite.type = "button";
      favorite.className = "btn small secondary";
      const isFavorite = state.favoriteRecipeIds.has(recipe.id);
      favorite.textContent = isFavorite ? "★ Favorited" : "☆ Favorite";
      favorite.addEventListener("click", async () => {
        favorite.disabled = true;
        try {
          if (state.favoriteRecipeIds.has(recipe.id)) {
            await api("/recipes/favorites/" + recipe.id + "/", { method: "DELETE" });
            state.favoriteRecipeIds.delete(recipe.id);
          } else {
            await api("/recipes/favorites/", { method: "POST", body: { recipe_id: recipe.id } });
            state.favoriteRecipeIds.add(recipe.id);
          }
          renderRecipeCatalog();
        } catch (error) {
          favorite.disabled = false;
          showStatus("recipeStatus", error.message, "error");
        }
      });

      const log = document.createElement("button");
      log.type = "button";
      log.className = "btn small";
      log.textContent = "Log as meal";
      log.addEventListener("click", async () => {
        log.disabled = true;
        try {
          await api("/food-entries/", {
            method: "POST",
            body: {
              food_name: recipe.name,
              meal_slot: recipe.slot.toLowerCase(),
              quantity: 1,
              unit: "serving",
              calories_kcal: recipe.base_calories_kcal,
              protein_g: recipe.base_macros.p,
              carbs_g: recipe.base_macros.c,
              fat_g: recipe.base_macros.f,
              fiber_g: recipe.base_macros.fib
            }
          });
          await refreshRecords();
          showStatus("recipeStatus", recipe.name + " added to your private food diary.", "success");
        } catch (error) {
          showStatus("recipeStatus", error.message, "error");
        } finally {
          log.disabled = false;
        }
      });
      actions.append(favorite, log);
      card.appendChild(actions);
      grid.appendChild(card);
    });
    host.appendChild(grid);
  }

  function renderWorkoutCatalog() {
    const host = $("routineResults");
    if (!host) return;
    host.replaceChildren();
    if (!state.catalogRoutines.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "No routines found for these settings.";
      host.appendChild(empty);
      return;
    }
    const grid = document.createElement("div");
    grid.className = "catalog-grid";
    state.catalogRoutines.forEach((routine) => {
      const card = document.createElement("article");
      card.className = "catalog-card";
      const title = document.createElement("h3");
      title.textContent = routine.title;
      const subtitle = document.createElement("p");
      subtitle.className = "muted";
      subtitle.textContent = routine.mode.toUpperCase() + " · " + routine.level + " · " + routine.exercise_links.length + " exercises";
      card.append(title, subtitle);
      const list = document.createElement("ol");
      routine.exercise_links.forEach((link) => {
        const exercise = link.exercise;
        const li = document.createElement("li");
        const name = document.createElement("strong");
        name.textContent = exercise.name;
        li.appendChild(name);
        const detail = document.createElement("p");
        detail.className = "muted";
        detail.textContent = exercise.detail + " · " + exercise.focus + " · " + exercise.muscles;
        li.appendChild(detail);
        const details = document.createElement("details");
        const summary = document.createElement("summary");
        summary.textContent = "View instructions and form tips";
        details.appendChild(summary);
        const steps = document.createElement("ol");
        exercise.steps.forEach((step) => {
          const stepItem = document.createElement("li");
          stepItem.textContent = step;
          steps.appendChild(stepItem);
        });
        details.appendChild(steps);
        const mod = document.createElement("p");
        mod.textContent = "Modification: " + exercise.modification;
        details.appendChild(mod);
        const mistake = document.createElement("p");
        mistake.textContent = "Avoid: " + exercise.common_mistake;
        details.appendChild(mistake);
        li.appendChild(details);
        list.appendChild(li);
      });
      card.appendChild(list);
      const start = document.createElement("button");
      start.type = "button";
      start.className = "btn small";
      start.textContent = "Start this routine";
      start.addEventListener("click", async () => {
        start.disabled = true;
        try {
          await api("/workout-sessions/", {
            method: "POST",
            body: { title: routine.title, notes: "Started from the V1 exercise catalogue." }
          });
          await refreshRecords();
          showStatus("routineStatus", routine.title + " started. Log sets in the Workout sessions panel.", "success");
        } catch (error) {
          showStatus("routineStatus", error.message, "error");
        } finally {
          start.disabled = false;
        }
      });
      card.appendChild(start);
      grid.appendChild(card);
    });
    host.appendChild(grid);
  }

  async function refreshRecipeCatalog() {
    const params = new URLSearchParams();
    const diet = $("recipeDiet").value;
    const slot = $("recipeSlot").value;
    const search = $("recipeSearch").value.trim();
    if (diet) params.set("diet_style", diet);
    if (slot) params.set("slot", slot);
    if (search) params.set("search", search);
    state.catalogRecipes = await api("/recipes/?" + params.toString());
    renderRecipeCatalog();
  }

  async function refreshWorkoutCatalog() {
    const params = new URLSearchParams({
      mode: $("routineMode").value,
      level: $("routineLevel").value
    });
    state.catalogRoutines = await api("/workout-routines/?" + params.toString());
    renderWorkoutCatalog();
  }

  async function loadCatalogs() {
    const [recipes, favorites, routines] = await Promise.all([
      api("/recipes/?diet_style=" + encodeURIComponent(state.profile.diet_type || "balanced")),
      api("/recipes/favorites/"),
      api("/workout-routines/?mode=" + encodeURIComponent(state.profile.workout_mode || "home") + "&level=" + encodeURIComponent(state.profile.fitness_level || "beginner"))
    ]);
    state.catalogRecipes = recipes;
    state.favoriteRecipeIds = new Set(favorites.map((item) => item.recipe.id));
    state.catalogRoutines = routines;
    renderRecipeCatalog();
    renderWorkoutCatalog();
    $("recipeDiet").value = state.profile.diet_type || "balanced";
    $("routineMode").value = state.profile.workout_mode || "home";
    $("routineLevel").value = state.profile.fitness_level || "beginner";
  }

  async function loadData() {
    setDateDefaults();
    const [account, profile, households, weights, measures, foods, waters, meals, groceries, workouts, fastings, goals] = await Promise.all([
      api("/me/"), api("/profile/"), api("/households/"),
      api("/weight-entries/"), api("/body-measurements/"),
      api("/food-entries/"), api("/water-entries/"),
      api("/meal-plan-entries/"), api("/grocery-lists/"),
      api("/workout-sessions/"), api("/fasting-sessions/"), api("/goals/")
    ]);
    state.account = account;
    state.profile = profile;
    state.households = households;
    state.weights = weights;
    state.measures = measures;
    state.foods = foods;
    state.waters = waters;
    state.meals = meals;
    state.groceries = groceries;
    state.workouts = workouts;
    state.fastings = fastings;
    state.goals = goals;
    await loadChildRecords();
    renderAll();
    await loadCatalogs();
    $("appLoading").hidden = true;
    $("appContent").hidden = false;
  }

  function optionalHouseholdValue(id) {
    const value = $(id).value;
    return value ? Number(value) : null;
  }

  function bindForm(id, handler) {
    $(id).addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.submitter;
      if (button) button.disabled = true;
      try {
        await handler(new FormData(event.currentTarget));
      } catch (error) {
        const statusId = event.currentTarget.dataset.status;
        if (statusId) showStatus(statusId, error.message, "error");
      } finally {
        if (button) button.disabled = false;
      }
    });
  }

  bindForm("profileForm", async (form) => {
    const body = {
      display_name: form.get("display_name"),
      unit_system: form.get("unit_system"),
      timezone_name: form.get("timezone_name"),
      age: Number(form.get("age")),
      gender: form.get("gender"),
      height_cm: Number(form.get("height_cm")),
      start_weight_kg: Number(form.get("start_weight_kg")),
      current_weight_kg: Number(form.get("current_weight_kg")),
      goal_weight_kg: Number(form.get("goal_weight_kg")),
      activity_multiplier: Number(form.get("activity_multiplier")),
      daily_deficit_kcal: Number(form.get("daily_deficit_kcal")),
      diet_type: form.get("diet_type"),
      workout_mode: form.get("workout_mode"),
      fitness_level: form.get("fitness_level")
    };
    [
      "share_weight_history", "share_body_measurements", "share_food_diary",
      "share_water_logs", "share_meal_plans", "share_grocery_lists",
      "share_workout_history", "share_workout_plans", "share_fasting_sessions",
      "share_goals"
    ].forEach((key) => { body[key] = form.get(key) === "on"; });
    state.profile = await api("/profile/", { method: "PATCH", body });
    renderProfile();
    showStatus("profileStatus", "Profile and sharing settings saved.", "success");
  });

  bindForm("weightForm", async (form) => {
    const body = {
      weight_kg: form.get("weight_kg"),
      note: form.get("note"),
      household: optionalHouseholdValue("weightHousehold")
    };
    if (!body.household) delete body.household;
    await api("/weight-entries/", { method: "POST", body });
    $("weightForm").reset();
    await refreshRecords();
    showStatus("weightStatus", "Weight entry saved.", "success");
  });

  bindForm("measureForm", async (form) => {
    const body = {
      waist_cm: form.get("waist_cm") || null,
      hip_cm: form.get("hip_cm") || null,
      chest_cm: form.get("chest_cm") || null,
      household: optionalHouseholdValue("measureHousehold")
    };
    if (!body.household) delete body.household;
    await api("/body-measurements/", { method: "POST", body });
    $("measureForm").reset();
    await refreshRecords();
    showStatus("measureStatus", "Body measurement saved.", "success");
  });

  bindForm("waterForm", async (form) => {
    const body = { amount_ml: Number(form.get("amount_ml")), household: optionalHouseholdValue("waterHousehold") };
    if (!body.household) delete body.household;
    await api("/water-entries/", { method: "POST", body });
    $("waterForm").reset();
    await refreshRecords();
    showStatus("waterStatus", "Water entry saved.", "success");
  });

  bindForm("mealForm", async (form) => {
    const body = {
      plan_date: form.get("plan_date"),
      meal_slot: form.get("meal_slot"),
      title: form.get("title"),
      servings: form.get("servings") || "1",
      household: optionalHouseholdValue("mealHousehold")
    };
    if (!body.household) delete body.household;
    await api("/meal-plan-entries/", { method: "POST", body });
    $("mealForm").reset();
    setDateDefaults();
    await refreshRecords();
    showStatus("mealStatus", "Meal plan entry saved.", "success");
  });

  bindForm("groceryForm", async (form) => {
    const body = {
      name: form.get("name"),
      week_of: form.get("week_of"),
      household: optionalHouseholdValue("groceryHousehold")
    };
    if (!body.household) delete body.household;
    await api("/grocery-lists/", { method: "POST", body });
    $("groceryForm").reset();
    setDateDefaults();
    await refreshRecords();
    showStatus("groceryStatus", "Grocery list created.", "success");
  });

  bindForm("fastingForm", async (form) => {
    const body = {
      target_hours: form.get("target_hours"),
      notes: form.get("notes"),
      household: optionalHouseholdValue("fastingHousehold")
    };
    if (!body.household) delete body.household;
    await api("/fasting-sessions/", { method: "POST", body });
    $("fastingForm").reset();
    await refreshRecords();
    showStatus("fastingStatus", "Fasting session started.", "success");
  });

  bindForm("foodForm", async (form) => {
    const body = {
      food_name: form.get("food_name"),
      meal_slot: form.get("meal_slot"),
      calories_kcal: form.get("calories_kcal") || null,
      protein_g: form.get("protein_g") || null,
      carbs_g: form.get("carbs_g") || null,
      fat_g: form.get("fat_g") || null,
      household: optionalHouseholdValue("foodHousehold")
    };
    if (!body.household) delete body.household;
    await api("/food-entries/", { method: "POST", body });
    $("foodForm").reset();
    await refreshRecords();
    showStatus("foodStatus", "Food entry saved.", "success");
  });

  bindForm("workoutForm", async (form) => {
    const body = {
      title: form.get("title"),
      notes: form.get("notes"),
      household: optionalHouseholdValue("workoutHousehold")
    };
    if (!body.household) delete body.household;
    await api("/workout-sessions/", { method: "POST", body });
    $("workoutForm").reset();
    await refreshRecords();
    showStatus("workoutStatus", "Workout session saved.", "success");
  });

  bindForm("goalForm", async (form) => {
    const body = {
      title: form.get("title"),
      metric_key: form.get("metric_key"),
      target_value: form.get("target_value"),
      unit: form.get("unit"),
      target_date: form.get("target_date") || null,
      household: optionalHouseholdValue("goalHousehold")
    };
    if (!body.household) delete body.household;
    await api("/goals/", { method: "POST", body });
    $("goalForm").reset();
    await refreshRecords();
    showStatus("goalStatus", "Goal saved.", "success");
  });

  bindForm("groceryItemForm", async (form) => {
    const listId = Number(form.get("grocery_list"));
    const body = {
      name: form.get("name"),
      quantity: form.get("quantity"),
      category: form.get("category")
    };
    await api("/grocery-lists/" + listId + "/items/", { method: "POST", body });
    $("groceryItemForm").reset();
    await refreshRecords();
    showStatus("groceryItemStatus", "Grocery item added.", "success");
  });

  bindForm("workoutSetForm", async (form) => {
    const sessionId = Number(form.get("session"));
    const body = {
      exercise_key: form.get("exercise_key"),
      exercise_name: form.get("exercise_name"),
      set_number: Number(form.get("set_number")),
      reps: form.get("reps") ? Number(form.get("reps")) : null,
      weight_kg: form.get("weight_kg") || null,
      duration_seconds: form.get("duration_seconds") ? Number(form.get("duration_seconds")) : null
    };
    await api("/workout-sessions/" + sessionId + "/sets/", { method: "POST", body });
    $("workoutSetForm").reset();
    await refreshRecords();
    showStatus("workoutSetStatus", "Exercise set logged.", "success");
  });

  bindForm("householdForm", async (form) => {
    const result = await api("/households/", { method: "POST", body: { name: form.get("name") } });
    $("householdForm").reset();
    await refreshHouseholds();
    showStatus("householdStatus", "Household created: " + result.name, "success");
  });

  bindForm("inviteForm", async (form) => {
    const householdId = Number(form.get("household"));
    await api("/households/" + householdId + "/invitations/", {
      method: "POST",
      body: { email: form.get("email"), role: form.get("role") }
    });
    $("inviteForm").reset();
    showStatus("inviteStatus", "Invitation email sent. It expires in 7 days.", "success");
  });

  async function refreshRecords() {
    const [weights, measures, foods, waters, meals, groceries, workouts, fastings, goals] = await Promise.all([
      api("/weight-entries/"), api("/body-measurements/"),
      api("/food-entries/"), api("/water-entries/"),
      api("/meal-plan-entries/"), api("/grocery-lists/"),
      api("/workout-sessions/"), api("/fasting-sessions/"), api("/goals/")
    ]);
    state.weights = weights; state.measures = measures; state.foods = foods;
    state.waters = waters; state.meals = meals; state.groceries = groceries;
    state.workouts = workouts; state.fastings = fastings; state.goals = goals;
    await loadChildRecords();
    renderAll();
  }

  async function refreshHouseholds() {
    state.households = await api("/households/");
    renderHouseholds();
  }

  let pendingV1Import = null;

  function renderV1ImportPreview(preview) {
    const host = $("v1ImportPreviewContent");
    host.replaceChildren();
    const counts = document.createElement("ul");
    counts.className = "muted";
    Object.entries(preview.counts || {}).forEach(([key, value]) => {
      const li = document.createElement("li");
      li.textContent = key.replaceAll("_", " ") + ": " + value;
      counts.appendChild(li);
    });
    host.appendChild(counts);

    const warnings = document.createElement("ul");
    warnings.className = "muted";
    (preview.warnings || []).forEach((warning) => {
      const li = document.createElement("li");
      li.textContent = warning;
      warnings.appendChild(li);
    });
    (preview.unsupported_fields || []).forEach((field) => {
      const li = document.createElement("li");
      li.textContent = "Not imported yet: " + field;
      warnings.appendChild(li);
    });
    const invalid = preview.invalid_entries_skipped || {};
    Object.entries(invalid).forEach(([key, value]) => {
      if (value > 0) {
        const li = document.createElement("li");
        li.textContent = "Invalid " + key.replaceAll("_", " ") + " skipped: " + value;
        warnings.appendChild(li);
      }
    });
    if (warnings.childNodes.length) {
      const heading = document.createElement("h4");
      heading.textContent = "Important notes";
      host.append(heading, warnings);
    }
    if (preview.already_imported) {
      const warning = document.createElement("p");
      warning.className = "status error";
      warning.textContent = "This exact profile backup has already been imported into this account.";
      host.appendChild(warning);
    }
    $("confirmV1ImportButton").disabled = Boolean(preview.already_imported);
    $("v1ImportPreview").hidden = false;
  }

  $("v1ImportForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    pendingV1Import = null;
    $("v1ImportPreview").hidden = true;
    const file = $("v1BackupFile").files && $("v1BackupFile").files[0];
    if (!file) {
      showStatus("importStatus", "Choose a V1 JSON backup file first.", "error");
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      showStatus("importStatus", "This backup is larger than the 2 MB import limit.", "error");
      return;
    }
    try {
      const backup = JSON.parse(await file.text());
      const profileId = $("v1ProfileChoice").value;
      const preview = await api("/imports/v1/preview/", {
        method: "POST",
        body: { backup, profile_id: profileId }
      });
      pendingV1Import = { backup, profileId };
      renderV1ImportPreview(preview);
      showStatus("importStatus", "Review the preview carefully. Existing records will be preserved; profile settings will be updated.", "success");
    } catch (error) {
      showStatus("importStatus", "Preview failed: " + error.message, "error");
    }
  });

  $("confirmV1ImportButton").addEventListener("click", async () => {
    if (!pendingV1Import) {
      showStatus("importStatus", "Preview a backup before confirming the import.", "error");
      return;
    }
    const button = $("confirmV1ImportButton");
    button.disabled = true;
    button.textContent = "Importing…";
    try {
      const result = await api("/imports/v1/commit/", {
        method: "POST",
        body: {
          backup: pendingV1Import.backup,
          profile_id: pendingV1Import.profileId,
          confirm: true
        }
      });
      pendingV1Import = null;
      $("v1BackupFile").value = "";
      $("v1ImportPreview").hidden = true;
      showStatus("importStatus", "Imported " + result.source_profile + " profile: " + result.counts.weight_entries + " weigh-ins, " + result.counts.food_entries + " food entries, and " + result.counts.body_measurements + " body measurements.", "success");
      await loadData();
    } catch (error) {
      showStatus("importStatus", "Import failed: " + error.message, "error");
      button.disabled = false;
      button.textContent = "Confirm and import this profile";
    }
  });

  $("recipeDiet").addEventListener("change", () => refreshRecipeCatalog().catch((e) => showStatus("recipeStatus", e.message, "error")));
  $("recipeSlot").addEventListener("change", () => refreshRecipeCatalog().catch((e) => showStatus("recipeStatus", e.message, "error")));
  $("recipeSearch").addEventListener("input", () => {
    if (window.__fitstartRecipeSearchTimer) clearTimeout(window.__fitstartRecipeSearchTimer);
    window.__fitstartRecipeSearchTimer = setTimeout(() => refreshRecipeCatalog().catch((e) => showStatus("recipeStatus", e.message, "error")), 250);
  });
  $("routineMode").addEventListener("change", () => refreshWorkoutCatalog().catch((e) => showStatus("routineStatus", e.message, "error")));
  $("routineLevel").addEventListener("change", () => refreshWorkoutCatalog().catch((e) => showStatus("routineStatus", e.message, "error")));

  $("exportDataButton").addEventListener("click", async () => {
    const button = $("exportDataButton");
    button.disabled = true;
    showStatus("exportStatus", "Preparing your private data export…");
    try {
      const response = await fetch("/api/v1/export/", {
        method: "GET",
        credentials: "same-origin",
        headers: { Accept: "application/json" }
      });
      if (!response.ok) {
        let message = "Export failed (" + response.status + ").";
        try {
          const errorBody = await response.json();
          if (errorBody.detail) message = errorBody.detail;
        } catch (_) {}
        throw new Error(message);
      }
      const data = await response.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "fitstart-v2-export.json";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      showStatus("exportStatus", "Your personal data export was downloaded. Keep the file private.", "success");
    } catch (error) {
      showStatus("exportStatus", error.message, "error");
    } finally {
      button.disabled = false;
    }
  });

  document.querySelectorAll("[data-scroll]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = $(button.dataset.scroll);
      target?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  loadData().catch((error) => {
    $("appLoading").textContent = error.message + " If your session expired, sign in again.";
  });
})();
