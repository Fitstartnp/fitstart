# FitStart V2 — Platform Architecture

## Goal

Evolve the current single-file browser planner into a self-hosted, multi-user web application. Keep the existing GitHub Pages app available as the stable legacy version while V2 is developed and tested separately.

V2 must support:
- Independent accounts for people using the service.
- Private personal profiles and activity records.
- Optional household spaces so two or more invited users can collaborate.
- Explicit sharing controls; a household membership must not automatically expose every private health/progress record.
- Server-side persistence, backups, account recovery, and administration.
- A deployment model that can run on the owner's domain and server.
- A validated import path for existing FitStart JSON backups.

## Recommended initial stack

Use a **modular monolith**, not microservices:

- **Backend:** Django 5.2 LTS (latest patch at implementation time) with Django REST Framework for a versioned JSON API. The server already has Python 3.12; Django 5.2 supports it and its published extended-support period reaches April 2028.
- **Database:** PostgreSQL 18, installed as a Windows service on the current candidate host.
- **Frontend:** Django templates and vanilla JavaScript ES modules initially. Preserve the current visual design while splitting the giant HTML/JavaScript file into page, component, state, and service modules. Introduce a Vite build only where it adds value; a wholesale React rewrite is not required.
- **Authentication:** Django's server-side account/session system, email verification and password reset. Use secure, same-origin, server-managed sessions and CSRF protection.
- **Application server:** Waitress (production-quality WSGI server with Windows support) bound only to 127.0.0.1.
- **Production edge:** Caddy as a Windows service, providing reverse proxying and automatic HTTPS.
- **Deployment:** Native Windows services initially. Keep PostgreSQL private and do not expose its port to the public internet. A Linux host or VM remains a future alternative if server OS strategy changes.

This stack is a starting recommendation, not a deployment assumption. Confirm the target server's operating system, architecture, RAM, storage, network access, and Docker availability before pinning package versions or writing production deployment files.

## Application boundaries

### Public/static catalogue
- Recipe catalogue and nutrition metadata.
- Exercise catalogue and instructional metadata.
- Public application assets and versioned frontend bundle.

Catalogue data is read-only to ordinary users. User-generated favourites, meal plans, modifications, and logs remain private or explicitly shared.

### Identity and tenancy
- **User:** one login identity per person; unique verified email.
- **Household:** optional shared workspace, not a shared login.
- **HouseholdMembership:** user, household, role, status, and invitation/acceptance metadata.
- **Invitation:** one-time, high-entropy, expiring invitation token; persist only a hash of the token; bind to an intended email where appropriate.
- **PersonalProfile:** personal preferences, units, goals, and display name.
- **SharingPolicy:** category-level preferences controlling what household members can see.

Initial roles:
- Platform administrator: operates the service and handles account/support administration.
- Household owner: manages their household and invites/removes members.
- Household member: collaborates only on records explicitly shared with that household.

Do not use a global activeProfileId from the browser as an authorization boundary. The backend must derive identity and permissions from the authenticated session on every request.

### Personal and shared data
Recommended domain areas:
- Body measurements and weight history.
- Nutrition targets, dietary preferences, allergens, and meal plans.
- Food diary and water logs.
- Fasting sessions.
- Workout plans, exercise sessions, sets, and personal records.
- Goals, check-ins, progress summaries, and favourites.
- Grocery lists and shared meal-planning items.

Each record must have an owner and, where collaboration is permitted, an explicit sharing scope such as private or household. Weight, measurements, food diary, and other potentially sensitive records should default to private. Shared meal plans and grocery lists can be household-visible by design.

## API conventions

- Version endpoints under /api/v1/.
- Use authenticated server-side sessions for browser clients; do not put access tokens, account secrets, or personal records in URLs.
- Enforce object-level authorization on every read, create, update, export, and delete.
- Scope all database queries to the authenticated user or an authorized household membership.
- Validate payloads server-side, use explicit serializers, limit upload sizes, and return consistent error formats.
- Do not accept a client-supplied user_id, household_id, or profile_id as proof of access.
- Add pagination for logs and catalogues; filter and sort on the server for large datasets.

## Security baseline

- Password hashes use a modern adaptive password-hashing scheme such as Argon2id; never store plaintext passwords.
- Secure, HttpOnly, SameSite cookies; HTTPS-only in production; session rotation/expiry; CSRF protection.
- Login, password reset, invitation, and sensitive account actions are rate-limited.
- Email verification and single-use, expiring password-reset links.
- Secrets and database credentials live in environment/secret storage, never in Git or frontend bundles.
- No GitHub Personal Access Token or Gist token is required by the running application.
- No health/progress records or credentials in query strings, URL fragments, analytics, or routine logs.
- Admin access is separate from ordinary users, protected with MFA where available, and not public by default.
- Audit security-sensitive events (login failures, membership changes, exports, deletion) without recording sensitive health payloads.
- Automated tests must verify cross-user and cross-household isolation, including direct-ID access attempts.

## Data migration and compatibility

- Keep the existing index.html as the V1 reference/legacy app until V2 reaches feature parity.
- Keep a documented importer for fitstart-progress-backup.json and the existing localStorage export shape.
- Validate and preview imports before committing them. Report rows that could not be imported; never silently drop data.
- Map the two existing V1 profiles to two separate V2 accounts. Invite and accept the second account before assigning that person's profile data.
- Do not import the old browser-stored GitHub token or Gist credentials.
- Provide user-controlled JSON export and account deletion in V2.

## Deployment shape

Initial production topology on the connected Windows Server candidate:

    Browser
      |
      | HTTPS (your domain)
      v
    Caddy Windows service :80/:443
      |
      | reverse proxy to 127.0.0.1:8000
      v
    Waitress -> Django + API + static frontend
      |
      | localhost/private TCP
      v
    PostgreSQL Windows service

    Scheduled encrypted database backup -> separate backup destination

Only ports 80/443 should be public. Waitress and PostgreSQL must bind to localhost/private interfaces; PostgreSQL must not be reachable from the public internet. Use a dedicated non-admin service identity, restricted file ACLs, encrypted off-server backups, and tested restores. Configure health checks, error reporting, security updates, and a staging environment before serving public accounts.

**Host inventory on 22 November 2026:** the connected device reports Windows Server 2022 Standard Evaluation, a netcup KVM virtual server, 16 GB RAM, eight logical processors, Python 3.12, and about 390 GB free on C:. Docker Desktop, IIS, and WSL are not installed; ports 80 and 443 had no listeners at the time of inspection. The evaluation edition is time-limited and must be converted to a valid licensed edition before a public production launch. No software has been installed and no firewall or DNS settings have been changed.

Docker Desktop is not supported on Windows Server 2022. Native Windows services are the practical first deployment path for this host. PostgreSQL's EDB Windows installer lists Server 2022 support; Waitress supports CPython on Windows; Caddy supports running as a Windows service and can manage HTTPS certificates.

DNS, firewall, Caddy, PostgreSQL, and backup instructions will be applied only after confirming the exact domain and production host.

## GDPR and privacy readiness

This app stores body measurements, weight history, food choices, activity, and related progress. Depending on the information and how it is used, some of it may constitute data concerning health under GDPR Article 9. Before opening registration to the public, determine the controller, purposes and lawful bases, any applicable Article 9 condition, retention periods, hosting/data-transfer arrangements, processors, and user rights. Publish clear privacy information and obtain specialist legal review; do not assume that a checkbox alone makes the service compliant.

## Build sequence

1. **Inventory and protect V1:** document current features/data shapes; preserve the current live site; rotate/revoke any credential ever exposed in public history before history cleanup.
2. **V2 foundation:** repository structure, environment configuration, Django project, PostgreSQL, Vite frontend build, tests, Docker development setup.
3. **Identity and tenancy:** registration, verification, login/logout, recovery, households, invitations, roles, sharing policies, admin controls.
4. **Data/API layer:** models, migrations, /api/v1/, validation, authorization tests, audit events.
5. **V1 data import:** validated preview/commit flow for exported backup data and a recovery/export path.
6. **Feature migration:** dashboard and goals; food diary/nutrition; recipes/groceries; workout logging; progress and charts; fasting and advanced tools.
7. **Staging and production:** server inventory, TLS/domain, secrets, database backups/restore, security review, usability tests, then controlled beta.
8. **History cleanup:** only after credentials have been revoked/rotated and V2 is safely branched/tagged; rewrite public Git history, force-push with coordination, and verify the cleaned remote history.

## Not in the first release

- Microservices or Kubernetes.
- Social feeds, public leaderboards, or public visibility of private health metrics.
- AI-generated medical or nutrition treatment recommendations.
- Payments/subscriptions.
- Mobile native apps; the web application should be responsive first.

## Decisions still needed

- Server OS/distribution and CPU architecture.
- Available RAM and disk space.
- Docker/Compose availability (or whether containers can be installed).
- Domain/subdomain and DNS control.
- Email sender/SMTP availability for verification and recovery.
- Whether registration starts invite-only or open to everyone.

The remaining deployment inputs are confirmation that this connected server is the intended public host, the domain/subdomain to use, Windows Server licensing status, and an email sender for verification/recovery.
