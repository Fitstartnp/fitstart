# FitStart V2

FitStart V2 is the server-backed, multi-account successor being developed alongside the existing V1 static app. The root `index.html` on `main` remains the live GitHub Pages app; V2 is **not publicly deployed**.

## Current V2 scope

- **Backend:** Django 5.2 LTS, Django REST Framework, PostgreSQL, Argon2 password hashing, Waitress, and WhiteNoise.
- **Accounts:** email-based accounts, server-side sessions, CSRF protection, password-reset views, and invitation-led onboarding. Invitations are single-use, expire after seven days, store only a token digest, and require proof of control of the invited mailbox.
- **Households:** owner/admin/member roles with explicit memberships. Membership alone does not expose personal records.
- **Privacy:** records are private by default. Sharing requires both the owner's category-level sharing switch and an explicit household selection. Other household members can read shared records but cannot edit or delete them. Exports contain only the current account's own records.
- **Personal records:** weight, body measurements, food diary, hydration, meal plans, groceries and grocery items, workout sessions and sets, fasting sessions, and goals.
- **Catalogue:** read-only recipe, exercise, and workout-routine catalogue endpoints, plus per-account recipe favourites.
- **Dashboard:** responsive server-rendered dashboard with forms and tables for the records above, profile and privacy controls, household invitations, catalogue browsing, nutrition estimates/progress, V1 backup preview/commit, and account JSON export.
- **V1 migration:** preview/commit supports one selected V1 profile per V2 account. It migrates profile settings, selected planner state, dated weigh-ins and available measurements, food diary entries, the current water-glass count (estimated at 250 ml per glass), completed workout set logs, and recipe favourites that match the V2 catalogue. Unmatched favourite names and uncompleted legacy workout plans are retained as compatibility state. Because V1 workout/food entries do not consistently include event timestamps, the importer reports that imported event dates/times are approximated at import time. It never imports GitHub/Gist credentials or the other partner's profile.
- **Data export:** authenticated JSON export includes the account's profile state, matched recipe favourites, owned records, and nested grocery/workout items; it excludes other household members' data even when shared with the account.

## Quality gates

GitHub Actions checks Django configuration, verifies migrations, runs Django's test suite against PostgreSQL 18, performs Django's production deployment checks with non-production CI settings, and parses the browser JavaScript with Node.

The tests cover account/household onboarding, private-by-default sharing, cross-account read/write isolation, record APIs, V1 import preview/commit/deduplication, catalogue access, export isolation, and dashboard rendering/static assets.

## Not yet production-ready

V2 is still a private beta build. Before inviting real users or migrating live personal data, complete and record:

- Browser-based end-to-end, mobile, accessibility, and cross-browser acceptance testing.
- Login/password-reset rate limiting and a reviewed administrator access/MFA policy.
- User account deletion and retention workflows.
- Encrypted off-host database backup, restore rehearsal, and recovery procedures.
- Production PostgreSQL/SMTP installation, a validated licensed host, confirmed domain/DNS, HTTPS, firewall rules, monitoring, and rollback rehearsal.
- A security and privacy review appropriate for personal fitness, nutrition, and body-measurement data.

Do not use real health or progress records in development/test environments. Keep secrets, `.env` files, database files, real user data, and exports out of Git. Nutrition and energy calculations are estimates, not medical measurements or treatment advice.

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
    python manage.py import_v1_catalog
    python manage.py test
    python manage.py runserver

In development, SQLite is used when `DB_NAME` is empty. Production requires PostgreSQL, a protected secret key, explicit allowed hosts and HTTPS/CSRF origins, secure cookies, SMTP, migrations, collected static assets, and Waitress behind the configured reverse proxy. Never use Django's development server in production.

See:
- [Platform architecture](../docs/PLATFORM-ARCHITECTURE.md)
- [Windows Server deployment plan](../docs/WINDOWS-SERVER-DEPLOYMENT.md)
- [V2 API reference](../docs/V2-API.md)
