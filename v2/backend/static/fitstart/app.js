(() => {
  "use strict";

  const state = { account: null, profile: null, households: [], weights: [], foods: [], workouts: [], goals: [] };
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

    const select = $("inviteHousehold");
    const previous = select.value;
    select.replaceChildren();
    state.households.forEach((item) => {
      const option = document.createElement("option");
      option.value = String(item.id);
      option.textContent = item.name + " (" + item.role + ")";
      select.appendChild(option);
    });
    if (state.households.some((item) => String(item.id) === previous)) select.value = previous;
    $("inviteButton").disabled = state.households.length === 0;
  }

  function renderProfile() {
    const profile = state.profile;
    $("displayName").value = profile.display_name || "";
    $("unitSystem").value = profile.unit_system;
    $("timezoneName").value = profile.timezone_name;
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

  function renderAll() {
    $("accountEmail").textContent = state.account.email;
    $("weightCount").textContent = String(state.weights.length);
    $("foodCount").textContent = String(state.foods.length);
    $("workoutCount").textContent = String(state.workouts.length);
    $("goalCount").textContent = String(state.goals.length);
    renderProfile();
    renderHouseholds();
    renderTable("weightTable", [
      { label: "Date", value: (r) => r.measured_on },
      { label: "Weight", value: (r) => r.weight_kg + " kg" },
      { label: "Note", value: (r) => r.note }
    ], state.weights, "No weight entries yet.");
    renderTable("foodTable", [
      { label: "Logged", value: (r) => new Date(r.logged_at).toLocaleString() },
      { label: "Food", value: (r) => r.food_name },
      { label: "Meal", value: (r) => r.meal_slot },
      { label: "Energy", value: (r) => r.calories_kcal == null ? "—" : r.calories_kcal + " kcal" }
    ], state.foods, "No food entries yet.");
    renderTable("workoutTable", [
      { label: "Started", value: (r) => new Date(r.started_at).toLocaleString() },
      { label: "Workout", value: (r) => r.title },
      { label: "Notes", value: (r) => r.notes }
    ], state.workouts, "No workout sessions yet.");
    renderTable("goalTable", [
      { label: "Goal", value: (r) => r.title },
      { label: "Metric", value: (r) => r.metric_key },
      { label: "Target", value: (r) => r.target_value + (r.unit ? " " + r.unit : "") },
      { label: "Status", value: (r) => r.status }
    ], state.goals, "No goals yet.");
  }

  async function loadData() {
    const [account, profile, households, weights, foods, workouts, goals] = await Promise.all([
      api("/me/"),
      api("/profile/"),
      api("/households/"),
      api("/weight-entries/"),
      api("/food-entries/"),
      api("/workout-sessions/"),
      api("/goals/")
    ]);
    state.account = account;
    state.profile = profile;
    state.households = households;
    state.weights = weights;
    state.foods = foods;
    state.workouts = workouts;
    state.goals = goals;
    renderAll();
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
      timezone_name: form.get("timezone_name")
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
    const [weights, foods, workouts, goals] = await Promise.all([
      api("/weight-entries/"), api("/food-entries/"),
      api("/workout-sessions/"), api("/goals/")
    ]);
    state.weights = weights; state.foods = foods; state.workouts = workouts; state.goals = goals;
    renderAll();
  }

  async function refreshHouseholds() {
    state.households = await api("/households/");
    renderHouseholds();
  }

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
