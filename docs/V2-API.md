# FitStart V2 API reference

Base path: `/api/v1/`

The API is same-origin and uses Django server-side sessions. It does not accept GitHub tokens, bearer tokens, or client-selected account IDs. The default API permission is authenticated access except for the minimal health endpoint.

## Session and CSRF

- Sign in at `/accounts/login/`.
- Sign out using the POST form at `/accounts/logout/`.
- Password reset starts at `/accounts/password-reset/`; reset completion uses the emailed link.
- For POST, PATCH, PUT, and DELETE requests from the browser, send the `csrftoken` cookie value in the `X-CSRFToken` header.
- Use `credentials: "same-origin"` for browser fetch calls.
- Invitation acceptance is CSRF-protected. The one-time invitation token is sent in an email URL fragment and is submitted in the POST body.
- API responses do not contain passwords, session cookies, or invitation token digests.

## Identity and profile

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health/` | Minimal application/database health check; no user details |
| GET | `/api/v1/me/` | Current authenticated account |
| GET | `/api/v1/profile/` | Current profile, planner compatibility state, and sharing preferences |
| PATCH | `/api/v1/profile/` | Update permitted current-account profile fields and sharing switches |

Profile PATCH accepts only:
- `display_name`
- `unit_system` (`metric` or `imperial`)
- `timezone_name` (IANA time zone)
- `age`, `gender`, `height_cm`, `start_weight_kg`, `current_weight_kg`, `goal_weight_kg`
- `activity_multiplier`, `daily_deficit_kcal`, `diet_type`, `workout_mode`, `fitness_level`
- `share_meal_plans`, `share_grocery_lists`, `share_workout_plans`, `share_workout_history`
- `share_weight_history`, `share_body_measurements`, `share_food_diary`, `share_water_logs`
- `share_fasting_sessions`, `share_goals`

All sharing switches default to false. Imported planner/fasting compatibility fields are returned by profile GET and preserved by export; they are not writable through the general profile PATCH endpoint. Unsupported fields, including account IDs and user IDs, are rejected.

## Households and invitations

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/households/` | List current user's active household memberships |
| POST | `/api/v1/households/` | Create a household; creator becomes owner |
| POST | `/api/v1/households/{household_id}/invitations/` | Owner/admin sends a seven-day invitation email |
| POST | `/api/v1/invitations/accept/` | Accept a single-use invitation |

Invitation notes:
- The invitation token is randomly generated; only its SHA-256 digest is stored.
- The raw token is sent in the email URL fragment, not in the HTTP request path or query string.
- A new invitee can create an account using the emailed invitation and a password. Possession of the email link verifies the invited address.
- Existing accounts must sign in with the invited account before accepting.
- Tokens expire after seven days, are single-use, and are never returned in API responses.
- Production must configure SMTP/email; production settings refuse console-email mode.

## Personal activity resources

Each resource is authenticated and supports GET collection, POST create, GET detail, PATCH/PUT detail, and DELETE detail unless noted.

| Collection path | Model | Sharing preference |
|---|---|---|
| `/weight-entries/` | WeightEntry | `share_weight_history` |
| `/body-measurements/` | BodyMeasurement | `share_body_measurements` |
| `/food-entries/` | FoodEntry | `share_food_diary` |
| `/water-entries/` | WaterEntry | `share_water_logs` |
| `/meal-plan-entries/` | MealPlanEntry | `share_meal_plans` |
| `/grocery-lists/` | GroceryList | `share_grocery_lists` |
| `/workout-sessions/` | WorkoutSession | `share_workout_history` |
| `/fasting-sessions/` | FastingSession | `share_fasting_sessions` |
| `/goals/` | Goal | `share_goals` |

Nested resources:

| Method | Path | Purpose |
|---|---|---|
| GET / POST | `/api/v1/grocery-lists/{list_id}/items/` | List or add items to a visible grocery list |
| GET / PATCH / DELETE | `/api/v1/grocery-lists/{list_id}/items/{item_id}/` | Read a shared item; only its list owner can change or delete it |
| GET / POST | `/api/v1/workout-sessions/{session_id}/sets/` | List or add sets to a visible workout |
| GET / PATCH / DELETE | `/api/v1/workout-sessions/{session_id}/sets/{set_id}/` | Read a shared set; only its workout owner can change or delete it |

## Catalogue and favourites

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/recipes/` | Browse/search/filter the read-only recipe catalogue |
| GET | `/api/v1/recipes/{id}/` | Read one recipe |
| GET | `/api/v1/exercises/` | Browse the read-only exercise catalogue |
| GET | `/api/v1/exercises/{id}/` | Read one exercise |
| GET | `/api/v1/workout-routines/` | Browse workout routines |
| GET | `/api/v1/workout-routines/{id}/` | Read one routine |
| GET / POST | `/api/v1/recipes/favorites/` | List or add the current user's recipe favourites |
| DELETE | `/api/v1/recipes/favorites/{recipe_id}/` | Remove one of the current user's favourites |

Catalogue entries are shared read-only definitions. Favourites belong to the signed-in account and are not visible to another household member unless a future explicit feature says otherwise.

## Personal data export

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/export/` | Download the current account's profile and personally owned records as JSON |

The export requires authentication. It includes the current account's own profile, V1 planner/fasting compatibility state, matched recipe favourites, and personally owned records, including nested grocery items and workout sets. It excludes records owned by other household members—even when those records are shared and visible in the dashboard. The response is marked `Cache-Control: no-store` and sent as `fitstart-v2-export.json`.

The export does not include passwords, session identifiers/cookies, invitation tokens, GitHub/Gist credentials, or the original raw V1 backup.

## V1 backup migration

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/imports/v1/preview/` | Validate one selected profile from a V1 JSON backup and report import counts/warnings |
| POST | `/api/v1/imports/v1/commit/` | Import the selected profile after explicit confirmation |

Both endpoints require an authenticated session and CSRF token. The request body contains:
- `backup`: parsed `fitstart-progress-backup.json` content.
- `profile_id`: `husband` or `wife`.
- `confirm`: `true` on the commit endpoint only.

The importer handles one profile at a time and maps profile/body settings, planner variation/slot state, exercise completion state, streak/date values, fasting protocol and elapsed state, dated weigh-ins, available body measurements, food diary entries, and the current water-glass count (estimated at 250 ml per glass). Completed V1 workout set logs are imported into a V2 workout session; because V1 does not retain a reliable session timestamp, the workout uses the import time. Uncompleted workout plans are retained as legacy compatibility state. Favourite recipe names are matched to the V2 catalogue and imported where possible; unmatched names remain in the profile for reference.

The importer never imports GitHub/Gist credentials or the other partner's profile. Invalid rows/sets and unmatched favourite names are reported in the preview/commit response. The server stores an import fingerprint and aggregate counts, not the original raw backup. Existing V2 records are preserved and new rows are appended. Repeating the exact same selected profile backup in the same account returns HTTP 409.

## Record authorization rules

1. The server assigns record ownership from the authenticated session. The client cannot assign another owner.
2. Private records are visible only to their owner.
3. To share a record, the owner must enable that category's sharing switch and explicitly choose a household in which the owner is an active member.
4. Household members can read records explicitly shared with that household while their membership is active.
5. Household members cannot update or delete another person's records, even when those records are shared.
6. Turning a sharing switch off immediately removes that person's shared records from other household members' query results.
7. Exports are restricted to records owned by the current account, not all records visible to that account.

## Known release limitations

The V2 dashboard is a private beta. It still needs broader browser end-to-end, mobile, accessibility, and cross-browser acceptance testing. Production deployment, account deletion/retention, login and password-reset rate limiting, administrator access/MFA policy, encrypted off-host backups, and a tested restore/rollback procedure are not yet complete. Do not use it with real personal records until those gates are closed.
