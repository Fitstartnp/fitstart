# Windows Server deployment plan (FitStart V2)

This is a staged plan for the connected netcup KVM host, which reported Windows Server 2022 Standard Evaluation on 22 November 2026. It is not an installation script. Do not run production installation steps until the owner has confirmed the host, domain, licensing, and maintenance window.

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
4. Confirm the exact domain/subdomain and configure DNS A/AAAA records to the public server address.
5. Ensure the provider firewall and Windows Firewall allow inbound TCP 80 and 443 only for the web service. Keep RDP restricted to trusted source IPs or a VPN; never expose PostgreSQL.
6. Arrange outbound email/SMTP for verification, invitations, and password recovery.
7. Create a non-admin service account, e.g. `FitStartSvc`, with read/execute access to code and write access only to logs/uploads/backups.
8. Decide backup destination and retention. A backup on the same server is not sufficient by itself.

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

## Example Caddyfile (replace the placeholder domain)

```caddyfile
fitstart.example.com {
    encode zstd gzip
    reverse_proxy 127.0.0.1:8000
}
```

Caddy must be installed as a Windows service and its configuration/data directories must be writable by its dedicated service identity. Do not share private keys or certificate storage.

## Django production settings checklist

- DEBUG=false.
- SECRET_KEY from protected server-side configuration.
- ALLOWED_HOSTS contains only the chosen hostname(s).
- CSRF_TRUSTED_ORIGINS contains the exact HTTPS origin(s).
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

Keep V1 (the current root `index.html` on `main`) online until V2 has passed the beta acceptance checklist. Use a staging hostname first. Do not point the public domain to V2 until accounts, data isolation, migration, backups, recovery, and security checks are signed off.
