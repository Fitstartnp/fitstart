# FitStart V2

This folder contains the new multi-user platform. The root `index.html` remains the V1 GitHub Pages app and is not being replaced during the V2 build.

## Current status

- **Architecture and hosting:** Windows Server 2022 self-hosting plan documented for the connected netcup KVM host. No production software, DNS, firewall, or service configuration has been changed.
- **Backend:** Django 5.2 LTS, Django REST Framework, PostgreSQL driver, Argon2 password hashing, Waitress, and WhiteNoise.
- **Identity:** custom email-based accounts, session login/logout, password reset views, and Django admin registration.
- **Households:** owner/admin/member roles, invitation email API, seven-day single-use token, SHA-256 token digest at rest, verified-email acceptance, CSRF-protected acceptance page.
- **Profile and privacy:** personal profile auto-created for new accounts; sharing switches default to private.
- **Data model:** weight history, body measurements, food diary, water entries, meal plan entries, grocery lists/items, workout sessions/sets, fasting sessions, and goals.
- **API:** owner-scoped CRUD for weight, body measurements, food, water, meal plans, grocery lists/items, workouts/sets, fasting, and goals. Shared reads are allowed only for the selected household/category; writes remain owner-only. Shared records become private again when their owner leaves the household.
- **Frontend:** responsive first dashboard for summary counts, weight, measurements, food, hydration, meal planning, grocery lists/items, workouts/sets, fasting, goals, profile/sharing settings, household creation, and invitation sending. Workout and fasting sessions can be ended by their owners.
- **Tests:** local Windows checkout passes 37 Django tests, including dashboard render/static assets, invitation onboarding, record CRUD, private-by-default sharing, and household read/write isolation. GitHub Actions runs the same suite.
- **Still pending:** recipe and exercise catalogue migration; nutrition-target/calculator interface; V1 JSON backup import/export; recipe and exercise catalogue migration; full browser interaction and accessibility testing; production PostgreSQL/SMTP installation and deployment; domain and TLS setup.

## Local development (Windows PowerShell)

From the repository root:

    cd v2/backend
    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    $env:DJANGO_DEBUG = "true"
    $env:DJANGO_SECRET_KEY = "development-only"
    python manage.py makemigrations --check --dry-run
    python manage.py migrate
    python manage.py createsuperuser
    python manage.py test
    python manage.py runserver

In development, SQLite is used if `DB_NAME` is not set. Production must set DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, and DB_PORT to connect to PostgreSQL, plus production hostname, HTTPS/CSRF origins, secret key, and SMTP settings. Production must run migrations and `collectstatic` before starting Waitress behind Caddy. Never use `runserver` in production.

## Important

- Do not use real health data in early development or tests.
- Do not commit secrets, .env files, database files, user data, or exported backups.
- Invitation acceptance requires an authenticated account whose email is already verified, or creates an account through an invitation emailed to that address.
- Keep the current V1 Pages deployment stable until the V2 import, feature migration, authorization, restore, and security acceptance checks pass.

See:
- [Platform architecture](../docs/PLATFORM-ARCHITECTURE.md)
- [Windows Server deployment plan](../docs/WINDOWS-SERVER-DEPLOYMENT.md)
- [V2 API reference](../docs/V2-API.md)
