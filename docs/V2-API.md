# FitStart V2 API reference

Base path: `/api/v1/`

The current API is same-origin and uses Django server-side sessions. It is intended for the V2 browser frontend; it does not accept GitHub tokens, bearer tokens, or client-selected account IDs.

## Session and CSRF

- Sign in at `/accounts/login/`.
- Sign out via the POST form at `/accounts/logout/`.
- For POST, PATCH, PUT, and DELETE requests from the browser, send the `csrftoken` cookie value in the `X-CSRFToken` header.
- Use `credentials: "same-origin"` for browser fetch calls.
- API responses do not contain passwords, session cookies, or invitation token digests.

## Identity and profile

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health/` | Minimal application/database health check |
| GET | `/api/v1/me/` | Current authenticated account |
| GET | `/api/v1/profile/` | Current account's personal preferences and sharing settings |
| PATCH | `/api/v1/profile/` | Update only the current account's profile and sharing switches |

Profile PATCH accepts only:
- `display_name`
- `unit_system` (`metric` or `imperial`)
- `timezone_name` (IANA time zone)
- `share_meal_plans`
- `share_grocery_lists`
- `share_workout_plans`
- `share_workout_history`
- `share_weight_history`
- `share_body_measurements`
- `share_food_diary`
- `share_water_logs`
- `share_fasting_sessions`
- `share_goals`

All sharing switches default to false. Unsupported fields, including account IDs and user IDs, are rejected.

## Households and invitations

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/households/` | List the current user's active household memberships |
| POST | `/api/v1/households/` | Create a household; creator becomes owner |
| POST | `/api/v1/households/{household_id}/invitations/` | Owner/admin sends a seven-day invitation email |
| POST | `/api/v1/invitations/accept/` | Accept a one-time invitation |

Invitation notes:
- The invitation token is generated randomly; only its SHA-256 digest is stored.
- The raw token is sent in the email URL fragment, not in the HTTP request path or query string.
- Invitation acceptance requires the intended verified account, or creates the new account using the invited address.
- Existing accounts must sign in before accepting.
- Tokens expire after seven days, are single-use, and are never returned in API responses.
- Production must configure SMTP/email. The production settings deliberately refuse console email mode.

## V1 backup migration

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/imports/v1/preview/` | Validate one selected profile from a V1 JSON backup and report import counts |
| POST | `/api/v1/imports/v1/commit/` | Import the selected profile after explicit confirmation |

Both endpoints require an authenticated session and CSRF token. The request body contains:
- `backup`: the parsed V1 `fitstart-progress-backup.json` object.
- `profile_id`: `husband` or `wife`.
- `confirm`: `true` on the commit endpoint only.

The importer maps profile/body settings, V1 weigh-ins, waist measurements attached to weigh-ins, food diary entries, and the current V1 water-glass count. It uses 250 ml per V1 glass as an estimate. V1 food entries did not contain timestamps, so imported food rows receive the import timestamp. Existing V2 logs are preserved and new rows are appended. The selected profile settings are updated on the current V2 account.

The importer does not import GitHub/Gist credentials. It does not import the other partner's profile. It reports unsupported V1 fields such as detailed exercise completions, workout set logs, favourites, and fasting state; these remain to be migrated separately. The server stores only an import fingerprint and aggregate counts, not the original backup JSON. A repeat of the exact same selected profile backup in the same account returns HTTP 409.

## Personal activity resources

Each resource supports:
- GET collection
- POST create
- GET detail
- PATCH detail
- PUT detail
- DELETE detail

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

Nested child resources:

| Method | Path | Purpose |
|---|---|---|
| GET / POST | `/api/v1/grocery-lists/{list_id}/items/` | List or add items to a visible grocery list |
| GET / PATCH / DELETE | `/api/v1/grocery-lists/{list_id}/items/{item_id}/` | Read a shared item or mutate it as the list owner |
| GET / POST | `/api/v1/workout-sessions/{session_id}/sets/` | List or add exercise sets to a visible workout |
| GET / PATCH / DELETE | `/api/v1/workout-sessions/{session_id}/sets/{set_id}/` | Read a shared set or mutate it as the workout owner |

Prefix each resource path with `/api/v1`.

## Record authorization rules

1. The server sets record ownership from the authenticated session. The client cannot assign another owner.
2. Private records are visible only to their owner.
3. To share a record, the owner must enable that category's sharing switch and explicitly choose a household that the owner actively belongs to.
4. Household members can read records explicitly shared with that household while their membership is active.
5. Household members cannot update or delete another person's records, even when those records are shared.
6. Changing the sharing switch to false immediately removes that person's shared records from household-member query results.
7. All reads, writes, exports, and deletes must continue to enforce these rules at the server query layer.

## Not yet exposed as endpoints

Recipe catalogue, micronutrient calculations, static exercise catalogue and import/export/V1 backup import are still pending migration into V2. The V2 dashboard currently has forms and tables for weight, body measurements, food, water, meal plans, grocery lists/items, workout sessions/sets, fasting sessions, goals, profile privacy, household creation, and invitations. All visible areas still need broader browser interaction, accessibility and usability testing.
