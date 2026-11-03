# OpenPrism security design

OpenPrism is a multi-user server for research data. This document describes how
user data are protected, how the server is hardened, and what operators must do.

## Architecture
| Component | Listens on | Purpose |
| --- | --- | --- |
| Application | `0.0.0.0:5000`, HTTPS (cheroot) | users: sign-in, encrypted project storage, analyses |
| Administration console | `127.0.0.1:47219` only | first-run setup, accounts, limits, backups |

The administration console refuses every request whose source address is not a
loopback address **and** whose `Host` header is not `localhost`/`127.0.0.1`/`[::1]`
(protection against DNS rebinding). The application has no administration API at
all; its static files do not include the console page. Until the first-run setup
has created an administrator, the application refuses all API access.

Administrator accounts are a separate table, cannot sign in to the application and
have no API that returns project contents or key material.

## End-to-end encryption
| Item | Where it exists |
| --- | --- |
| Password | only in the user's browser |
| Key-encryption key (KEK) = PBKDF2-SHA-256(password, salt, 600 000)[0:32] | only in the browser |
| Authentication key = PBKDF2(…)[32:64] | sent at sign-in; the server stores `scrypt(auth key)` |
| Data key (random AES-256) | browser memory / IndexedDB as a **non-extractable** CryptoKey; server stores it only wrapped by the KEK and by the recovery key |
| Recovery key (160 bit, shown once) | with the user (paper, password manager) |
| Projects and project names | server stores AES-256-GCM ciphertext only (`{format:"openprism-e2e", iv, ct}`); plaintext is refused |
| Local crash-recovery copy | browser `localStorage`, encrypted with the data key, wiped at sign-out |

* Unknown user IDs receive a deterministic fake salt (HMAC of the user ID with a
  server secret), so the salt endpoint does not reveal which accounts exist.
* Password change re-wraps the data key; projects need no re-encryption.
* An administrator's one-time password restores **sign-in only**. The data key stays
  wrapped by the old KEK; the user restores access with the recovery key, or starts
  with a new key (old projects then remain unreadable).
* **Limitation:** statistics run in the server's Python engine; the table being
  analyzed is sent over HTTPS for that request, processed in memory in a sandboxed
  worker, and never stored or logged. Stored data are end-to-end encrypted; data in
  computation are protected by TLS and process isolation.
* Encrypted export files use their own password (AES-256-GCM, PBKDF2 600 000).

## Sessions and requests
* 256-bit random session tokens; only SHA-256 hashes stored; idle 7 days / absolute 30
  days (admin: 2 h idle); revoked on sign-out, password change, disable and deletion.
* Cookies: `HttpOnly`, `SameSite=Strict`, `Secure` on HTTPS. Separate cookie names for
  the application and the console.
* CSRF: `SameSite=Strict` **and** a mandatory custom header (`X-OpenPrism` /
  `X-OpenPrism-Admin`) on every state-changing call **and** an `Origin` check.
* Brute force: failures counted per user ID, per IP and per administrator name; lockouts
  grow from 60 s to 1 h; equal-time responses for unknown users; generic messages.
  Registrations and reset requests are rate-limited per IP.
* Headers: strict CSP (`script-src 'self'`, no inline scripts, `object-src 'none'`,
  `frame-ancestors 'self'`, `base-uri 'none'`), `nosniff`, `X-Frame-Options`,
  `Referrer-Policy: no-referrer`, COOP/CORP, `Permissions-Policy`, HSTS on HTTPS,
  `Cache-Control: no-store` for APIs.
* Injection: SQL parameter binding only; user-defined equations use a whitelisting AST
  interpreter (no `eval`), max 2 000 characters / 600 nodes.
* Errors: internal details are logged server-side and never returned. The access log
  records address, method, path, status and duration — never bodies, query strings or
  cookies.

## Resource limits
| Limit | Default | Configurable |
| --- | --- | --- |
| Request body | 40 MB (console 1 MB) | code |
| Upload | 30 MB, 200 000 rows | code |
| Table per analysis | 2 000 000 cells, 2 000 data sets | code |
| Storage per user | 256 MB (warning at 128 MB) | console, per user and default |
| Project size | 25 MB | console |
| RAM per analysis | 1 024 MB (`RLIMIT_AS` in a forked worker) | console |
| CPU per analysis | 60 s (`RLIMIT_CPU` + wall-clock timeout) | console |
| Analyses per minute | 120, max 2 concurrent | console |
| Server threads | 32 | `OPENPRISM_THREADS` |

## Deployment checklist
1. Run `python run.py` (or the systemd unit in `deploy/`, which adds sandboxing:
   `ProtectSystem=strict`, `NoNewPrivileges`, private /tmp, `UMask=0077`).
2. Complete the first-run setup at `http://127.0.0.1:47219/` on the server.
3. Prefer a certificate trusted by your browsers (`--cert/--key` or a reverse proxy
   with `--http`); the self-signed certificate is created with a P-256 key in `data/tls/`.
4. Decide on self-registration in the console (off = only administrators create accounts).
5. Allow only the application port in the firewall; never expose the console port.
6. Back up the data directory (database contains only hashes and ciphertext); keep
   `tls/key.pem` private.
7. Keep Python dependencies up to date.

## Reporting vulnerabilities
Please open a private security advisory on the repository rather than a public issue.
