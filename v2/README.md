# FitStart V2

This folder contains the new multi-user platform. The root `index.html` remains the V1 GitHub Pages app and is not being replaced during the V2 build.

## Current status

- Architecture and Windows Server deployment plan: documented.
- Backend foundation: being scaffolded.
- Database schema: first identity/household layer.
- Authentication, invitation acceptance, feature APIs, and V1 data importer: not yet production-complete.
- Hosting: not deployed. The existing V1 site remains the public site.

## Development

The backend currently targets Python 3.12, Django 5.2 LTS, Django REST Framework 3.18, and PostgreSQL 18. A local SQLite fallback is provided for developer tests only. Production must set database environment variables and use PostgreSQL.

See:
- [Platform architecture](../docs/PLATFORM-ARCHITECTURE.md)
- [Windows Server deployment plan](../docs/WINDOWS-SERVER-DEPLOYMENT.md)

Never commit production secrets, backup exports, database files, user information, or GitHub access tokens.
