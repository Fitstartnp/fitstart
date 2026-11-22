# FitStart V2

This folder contains the new multi-user platform. The root `index.html` remains the V1 GitHub Pages app and is not being replaced during the V2 build.

## Current status

- Architecture and Windows Server deployment plan: documented.
- Backend foundation: Django 5.2 LTS, Django REST Framework, PostgreSQL adapter, Argon2 password hashing, Waitress, and WhiteNoise.
- Identity: custom email-based account model and server-side sessions.
- Personal profiles: created automatically for new users; all sharing switches default to private.
- Households: owner/admin/member roles, one-time invitation tokens stored as hashes, invitation expiry/revocation state, and verified-email acceptance service.
- API: database health endpoint, authenticated current-account endpoint, and current-user-scoped household list.
- UI: sign-in, password reset, and authenticated placeholder dashboard.
- Initial tests: account manager, invitation and household service, API authentication/isolation, and private profile defaults.
- Not yet complete: public registration, email verification workflow and templates, invitation email delivery/UI, full CRUD APIs, domain data models (nutrition, workout, progress), V1 import, production deployment, and full browser interaction testing.

## Local development (Windows PowerShell)

From this directory:

    cd v2/backend
    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    $env:DJANGO_DEBUG = "true"
    $env:DJANGO_SECRET_KEY = "development-only"
    python manage.py makemigrations
    python manage.py migrate
    python manage.py createsuperuser
    python manage.py test
    python manage.py runserver

In development, SQLite is used if `DB_NAME` is not set. Production must set DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, and DB_PORT to connect to PostgreSQL. The production domain and CSRF origins must also be set before launch. Never use `runserver` in production.

## Important

- Do not use real health data in early development or tests.
- Do not commit secrets, .env files, database files, user data, or exported backups.
- Invitation acceptance requires an authenticated account whose email has already been verified. The email verification and delivery workflow is not yet implemented.
- Keep the current V1 Pages deployment stable until the V2 import, feature migration, authorization and security acceptance checks pass.

See:
- [Platform architecture](../docs/PLATFORM-ARCHITECTURE.md)
- [Windows Server deployment plan](../docs/WINDOWS-SERVER-DEPLOYMENT.md)
