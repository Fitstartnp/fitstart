# Windows Server deployment plan (FitStart V2)

This is the staged deployment plan for the connected netcup KVM host. The owner confirmed `lunasants.com` on 22 November 2026. The host reports Windows Server 2022 Standard Evaluation. This document records the intended configuration; public DNS, firewall, software installation, and production services must not be changed until the remaining licence, SMTP, backup, and exposure checks are ready.

## Target services

- Caddy Windows service: public HTTP/HTTPS on ports 80 and 443; automatic TLS; reverse proxy.
- Waitress Windows service: Django WSGI application bound to 127.0.0.1:8000 only.
- PostgreSQL 18 Windows service: database on localhost/private interface, never public.
- Django static files: served with WhiteNoise initially; Caddy may serve built static files later.
- Scheduled backup task: encrypted PostgreSQL dumps and application configuration backups to a separate destination.

Docker Desktop is not supported on Windows Server 2022. This project therefore uses native Windows services for the first host deployment rather than installing Docker Desktop.

## Software baseline

Use the latest supported patch release in each chosen series and record the exact installed version in the deployment record:

- Python 3.12 x64 (already present; verify patch version).
- Django 5.2 LTS with the current security patch.
- Django REST Framework 3.18.x.
- PostgreSQL 18 x64 (EDB installer documents Windows Server 2022 support).
- Waitress 3.0.x.
- Caddy 2.11.x Windows amd64 binary.

Reference links:
- Django supported releases: https://www.djangoproject.com/download/
- Django deployment checklist: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- DRF requirements: https://www.django-rest-framework.org/
- PostgreSQL Windows installer: https://www.postgresql.org/download/windows/
- Waitress documentation: https://docs.pylonsproject.org/projects/waitress/en/latest/
- Caddy Windows service: https://caddyserver.com/docs/running

## Host readiness gates

Before public launch:
1. Confirm the connected server is the intended host and the owner controls its recovery console.
2. Convert Windows Server Evaluation to a valid licensed edition (or provision an appropriately licensed alternative). Microsoft states the Server 2022 evaluation expires after 180 days.
3. Confirm CPU/RAM/storage allocation and ensure sufficient free RAM after ordinary server services are running.
4. Confirm the server's assigned static public IPv4 in the netcup control panel. On 22 November 2026, both the host's Ethernet interface and an outbound public-IP check reported `152.53.237.21`; verify that netcup confirms this address is static before changing DNS.
5. Configure Namecheap BasicDNS Host Records for `lunasants.com`:
   - Replace the four apex GitHub Pages A records (`185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`) with one A record: host `@`, value `152.53.237.21`.
   - Replace the current `www` CNAME target `imobht.github.io` with `lunasants.com`.
   - Do not change the BasicDNS nameservers.
   - Preserve all five Namecheap Email Forwarding MX records (`eforward1` through `eforward5.registrar-servers.com`) and the SPF TXT record `v=spf1 include:spf.efwd.registrar-servers.com ~all`. These are the existing inbound email-forwarding settings.
   - DNS currently shows no AAAA record for the apex or `www`.
   Namecheap's instructions: https://www.namecheap.com/support/knowledgebase/article.aspx/319/2237/how-can-i-set-up-an-a-address-record-for-your-domain/ and https://www.namecheap.com/support/knowledgebase/article.aspx/9646/2237/how-to-create-a-cname-record-for-your-domain/
6. Ensure the netcup provider firewall and Windows Firewall allow inbound TCP 80 and 443 only for the web service. Keep RDP restricted to trusted source IPs or a VPN; never expose PostgreSQL or Waitress port 8000.
7. Arrange a verified outbound SMTP provider for invitations and password recovery. The existing Namecheap email forwarding MX/SPF settings support inbound forwarding; they do not by themselves provide outbound SMTP credentials.
8. Create a non-admin service account, e.g. `FitStartSvc`, with read/execute access to code and write access only to logs/uploads/backups.
9. Decide backup destination and retention. A backup on the same server is not sufficient by itself.

## Installation sequence (not yet executed)

1. Update Windows Server and confirm reboot/recovery access.
2. Install PostgreSQL 18 using the EDB Windows installer. Use a strong unique database administrator password; create a separate least-privilege application database role and database. Configure PostgreSQL to accept only localhost connections unless a private network is explicitly required.
3. Create the application directory (suggested `C:\\FitStart\\app`) and a Python virtual environment. Install the pinned Python requirements.
4. Generate a random Django SECRET_KEY outside the repository. Store it in a machine-protected environment/config file with restrictive ACLs. Do not place secrets in Git, static JavaScript, or a public web directory.
5. Configure `.env` values: production DEBUG=false, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, secret key, database connection, email settings, and secure-cookie settings.
6. Apply Django migrations, run `manage.py import_v1_catalog` to load the 160 recipes and 80 exercise definitions, collect static assets, create the first platform administrator, and run `manage.py check --deploy`.
7. Run Waitress bound to `127.0.0.1:8000` under a Windows service wrapper with automatic restart and logs.
8. Install Caddy as a Windows service. Configure the confirmed domain to reverse-proxy to `127.0.0.1:8000`. Caddy obtains and renews certificates after DNS and inbound reachability are correct.
9. Open public 80/443 in both provider firewall and Windows Firewall. Keep 8000 and PostgreSQL private.
10. Verify HTTPS, redirects, secure cookie attributes, host allow-list, login/logout, CSRF, API authorization, and restore from backup before inviting beta users.

## Caddy configuration

The checked-in domain-specific configuration is `v2/deploy/Caddyfile`. It serves `lunasants.com` and permanently redirects `www.lunasants.com` to the canonical apex hostname. Caddy can obtain certificates only after both DNS names resolve to the server and inbound TCP 80/443 are reachable.

Caddy must be installed as a Windows service and its configuration/data directories must be writable by its dedicated service identity. Do not share private keys or certificate storage.

## Django production settings checklist

- DEBUG=false.
- SECRET_KEY from protected server-side configuration.
- `DJANGO_ALLOWED_HOSTS=lunasants.com,www.lunasants.com`.
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://lunasants.com,https://www.lunasants.com`.
- `FITSTART_PUBLIC_URL=https://lunasants.com` for invitation URLs.
- SESSION_COOKIE_SECURE=true and CSRF_COOKIE_SECURE=true behind HTTPS.
- SECURE_SSL_REDIRECT=true only after HTTPS is confirmed.
- SECURE_PROXY_SSL_HEADER is configured only for the trusted local Caddy reverse proxy.
- HSTS enabled only after all intended hostnames are confirmed to serve HTTPS.
- PostgreSQL credentials are unique and least-privilege.
- Argon2 password hasher enabled.
- Error logs exclude passwords, session IDs, invitation tokens, health data, and food diary contents.

Run Django's production deployment checks before launch. Never use `manage.py runserver` in production.

## Backup and restore

- Daily encrypted PostgreSQL custom-format dump to a separate destination.
- Keep a documented retention schedule (for example, 7 daily, 4 weekly, 6 monthly) adjusted to expected use and cost.
- Back up user-uploaded media and deployment configuration separately.
- Keep encryption keys separate from the backup files.
- Schedule a restore rehearsal into an isolated test database and document the outcome.
- Provide in-app JSON export and account deletion in addition to operator backups.

## Rollback

Keep V1 (the current root `index.html` on `main`) untouched as a code rollback while V2 is brought online. The apex domain currently resolves to GitHub Pages addresses and `www` currently aliases `imobht.github.io`; both URLs returned HTTP 404 during the DNS/site check on 22 November 2026. Changing the website A/CNAME records will route these names to FitStart V2. Keep email MX/TXT records unchanged. Do not switch DNS or open public web ports until PostgreSQL, SMTP, backup/restore, the Windows licence, and security checks are ready.
