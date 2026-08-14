# Supabase Auth API

A small FastAPI service that hands authentication over to **Supabase Auth** instead of storing
passwords itself. It exposes signup, login and logout, one open endpoint, and two endpoints that
only answer when the caller presents a valid JWT in the `Authorization` header.

Built stage by stage as an authentication practice project. If you are new to any of this, read
**[GUIDE.md](GUIDE.md)** — it explains every file, every status code and every concept used here.

---

## What it does

- **Registration and login** are delegated to Supabase, so no password ever touches this codebase.
- **Protected routes** verify the caller's access token with Supabase on every request.
- **One reusable dependency** (`require_auth`) does the header parsing and token verification, so a
  route handler never sees an unauthenticated caller.
- **Swagger UI** at `/docs` with a working **Authorize** padlock, so the whole API can be exercised
  from a browser.

## Tech stack

| Piece | What it's for |
|---|---|
| Python 3.10+ | Language |
| FastAPI | Web framework, and the source of the auto-generated Swagger UI |
| Uvicorn | The ASGI server that actually runs the app |
| supabase (Python SDK) | Talks to Supabase Auth |
| python-dotenv | Loads credentials from `.env` |

---

## Setup

### 1. Clone and enter the project

```bash
git clone https://github.com/Sultan-Abbas/supabase-auth-api.git
cd supabase-auth-api
```

### 2. Create a virtual environment and install dependencies

Windows (PowerShell):

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS / Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

### 3. Create your Supabase project

1. Sign up at [supabase.com](https://supabase.com) and create a new project.
2. Open **Project Settings → API Keys**.
3. Copy the **Project URL** and the **`anon` / `public`** key (newer projects call this the
   **publishable** key; it starts with `sb_publishable_`).

> **Never** use the `service_role` / secret key here. It bypasses Row Level Security entirely.

### 4. Configure environment variables

Copy the example file and fill in your own values:

```bash
copy .env.example .env
```

```env
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your_anon_public_key
PORT=3000
```

`SUPABASE_URL` is the project root — **not** the `/rest/v1/` path shown elsewhere in the dashboard.

`.env` is listed in `.gitignore` and must never be committed.

### 5. Turn off email confirmation (for local testing)

In the Supabase dashboard: **Authentication → Sign In / Providers → Email → Confirm email → off**.

With it on, every signup sends a confirmation email, logins fail until the link is clicked, and the
free tier's email quota (2/hour) blocks further signups. Leave it **on** in any real product.

---

## Run it

One command:

```bash
.venv\Scripts\python.exe run.py
```

Expected output:

```
Server running and connected to Supabase (https://your-project-ref.supabase.co)
Uvicorn running on http://127.0.0.1:3000
```

Then open **http://localhost:3000/docs**.

---

## API reference

| Method | Endpoint | Auth required | Success | Errors |
|---|---|:---:|---|---|
| `POST` | `/auth/signup` | ❌ | `201 Created` — the new Supabase user | `400` missing email/password, or Supabase rejected it |
| `POST` | `/auth/login` | ❌ | `200 OK` — `access_token`, `refresh_token`, user | `400` missing fields · `401` invalid credentials |
| `POST` | `/auth/logout` | ✅ | `204 No Content` | `401` missing or invalid token |
| `GET` | `/public/info` | ❌ | `200 OK` — public message | — |
| `GET` | `/protected/profile` | ✅ | `200 OK` — id, email, created_at, last_sign_in_at, role | `401` missing or invalid token |
| `GET` | `/protected/dashboard` | ✅ | `200 OK` — greeting + user id | `401` missing or invalid token |
| `GET` | `/` | ❌ | `200 OK` — health check | — |

Protected endpoints expect:

```
Authorization: Bearer <access_token>
```

### Status codes

| Code | When |
|---|---|
| `200 OK` | Successful login or read |
| `201 Created` | User registered |
| `204 No Content` | Logged out (no body by design) |
| `400 Bad Request` | Missing/malformed input, or Supabase rejected the signup |
| `401 Unauthorized` | Token missing, malformed, expired, or invalid credentials |
| `503 Service Unavailable` | Supabase itself is unreachable |

### Error format

Every error uses the same shape:

```json
{ "error": "Invalid or expired token" }
```

---

## Example requests

Sign up:

```bash
curl.exe -i -X POST http://localhost:3000/auth/signup -H "Content-Type: application/json" -d '{\"email\":\"you@example.com\",\"password\":\"password123\"}'
```

Log in and keep the token in a variable:

```bash
$r = Invoke-RestMethod -Uri http://localhost:3000/auth/login -Method Post -ContentType "application/json" -Body '{"email":"you@example.com","password":"password123"}'; $t = $r.access_token
```

Call a protected route:

```bash
curl.exe -i http://localhost:3000/protected/profile -H "Authorization: Bearer $t"
```

> On Windows PowerShell use `curl.exe`, not `curl` — `curl` is an alias for `Invoke-WebRequest`,
> which does not understand `-H` or `-d`. Quoting rules are covered in [GUIDE.md](GUIDE.md).

---

## Swagger UI

FastAPI generates interactive docs at **http://localhost:3000/docs**. The `HTTPBearer` security
scheme puts a padlock on the protected routes and an **Authorize** button at the top right.

![Swagger UI showing the Authorize button and padlocked protected routes](docs/swagger-ui.png)

To use it:

1. `POST /auth/login` → **Try it out** → **Execute** → copy the `access_token`
2. Click **Authorize**, paste the token (no `Bearer ` prefix — Swagger adds it), **Authorize** → **Close**
3. `GET /protected/profile` → **Try it out** → **Execute** → `200` with your user

---

## Project structure

```
supabase-auth-api/
├── app/
│   ├── config.py           # loads and validates .env
│   ├── supabase_client.py  # one shared Supabase client
│   ├── dependencies.py     # require_auth: the reusable token guard
│   ├── schemas.py          # request/response models
│   ├── main.py             # app, error handlers, router wiring
│   └── routers/
│       ├── auth.py         # /auth/signup, /auth/login, /auth/logout
│       ├── public.py       # /public/info
│       └── protected.py    # /protected/profile, /protected/dashboard
├── run.py                  # entry point: python run.py
├── requirements.txt
├── .env.example            # template — copy to .env
├── .gitignore              # ignores .env
├── GUIDE.md                # beginner walkthrough of the whole project
└── README.md
```

---

## Security notes

- `.env` is git-ignored; credentials never enter the repository.
- Login failures always return the same `401 Invalid login credentials`, so an attacker cannot use
  the error message to discover which email addresses are registered.
- A Supabase outage returns `503`, not `401` — an unreachable auth service must not be reported to
  clients as a bad token.
- Access tokens are verified with Supabase on **every** protected request; nothing is trusted from
  the token body without that check.
- Signing out revokes the refresh token. An already-issued access token stays valid until it
  expires (up to an hour) — that is Supabase's design, not a bug in this service.

## License

MIT
