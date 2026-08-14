# Beginner's Guide

A walkthrough of this project for someone who has not built an authenticated API before.
It covers the vocabulary, what every file does, how a request travels through the code, and the
errors you will actually hit while running it.

Read [README.md](README.md) first if you just want to run the thing.

---

## Table of contents

1. [The idea in one picture](#1-the-idea-in-one-picture)
2. [Vocabulary](#2-vocabulary)
3. [File by file](#3-file-by-file)
4. [The life of a request](#4-the-life-of-a-request)
5. [Status codes, and why each one](#5-status-codes-and-why-each-one)
6. [Talking to the API from the terminal](#6-talking-to-the-api-from-the-terminal)
7. [Using Swagger UI](#7-using-swagger-ui)
8. [Troubleshooting](#8-troubleshooting)
9. [Git basics used here](#9-git-basics-used-here)
10. [Ideas for going further](#10-ideas-for-going-further)

---

## 1. The idea in one picture

This server never stores a password. It asks Supabase to do that, and Supabase hands back a token.

```
┌──────────┐   1. email + password    ┌──────────────┐   2. checks the password   ┌────────────┐
│  Client  │ ───────────────────────▶ │  This API    │ ─────────────────────────▶ │  Supabase  │
│ (curl,   │                          │  (FastAPI)   │                            │    Auth    │
│  browser)│ ◀─────────────────────── │              │ ◀───────────────────────── │            │
└──────────┘   4. access_token (JWT)  └──────────────┘   3. token + user record   └────────────┘
     │
     │  5. later: GET /protected/profile
     │     Authorization: Bearer <token>
     ▼
┌──────────────┐   6. "is this token real?"   ┌────────────┐
│  This API    │ ───────────────────────────▶ │  Supabase  │
│              │ ◀─────────────────────────── │            │
└──────────────┘   7. yes, and here's the user└────────────┘
```

The important habit: step 6 happens on **every** protected request. The server never assumes a
token is good just because it looks like one.

---

## 2. Vocabulary

**Authentication (AuthN)** — proving *who* you are. Email + password.

**Authorization (AuthZ)** — deciding *what* you may do. This project stops at authentication; the
`/protected` routes only ask "are you logged in", not "are you an admin".

**Identity Provider (IdP)** — the outside service that owns accounts and passwords. Here: Supabase.
Others: Auth0, Firebase, Clerk.

**JWT (JSON Web Token)** — a string with three parts separated by dots:

```
eyJhbGciOiJFUzI1NiIs...  .  eyJpc3MiOiJodHRwczovL2Jl...  .  QzG0STnJNdb79R0J-C4Lpk...
└─────── header ───────┘     └─────── payload ────────┘     └────── signature ──────┘
      which algorithm            the claims: who you             proof the payload
      signed this                are, when it expires            was not edited
```

The first two parts are only **base64-encoded**, not encrypted — anyone can read them. Paste a token
into [jwt.io](https://jwt.io) and you will see your own email. What stops forgery is the signature:
change one byte of the payload and the signature no longer matches.

**Access token** — the short-lived JWT (about 1 hour) you send with each request.

**Refresh token** — a long-lived token whose only job is to obtain a new access token when the old
one expires, without asking the user to log in again.

**Bearer token** — "whoever bears this token gets in." Sent as:

```
Authorization: Bearer eyJhbGciOiJFUzI1NiIs...
```

There is no extra proof of identity, which is why a leaked token is as dangerous as a leaked
password until it expires.

**Middleware / dependency** — code that runs *before* your route handler. Express calls it
middleware; FastAPI calls it a dependency. Either way, it is the bouncer at the door.

**Environment variables** — settings kept outside the source code, in `.env`, so secrets never land
in git.

**anon key** — short for *anonymous*. The public API key used for requests by someone not logged in
yet (like a signup). Safe to ship in a frontend. Its evil twin, `service_role`, bypasses all
database security and must never appear in this project.

---

## 3. File by file

### `.env` — your secrets (never committed)

```env
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your_anon_public_key
PORT=3000
```

`.env.example` is the committed template with the values blanked out, so someone cloning the repo
knows what to fill in. `.gitignore` contains `.env`, which is what keeps the real one out of git.

### `app/config.py` — reads and checks the environment

```python
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True, encoding="utf-8-sig")
```

Points at the `.env` sitting next to the project root rather than trusting the current working
directory, so the app starts the same way no matter which folder you launch it from.
`encoding="utf-8-sig"` tolerates the invisible BOM character Windows editors like to add — without
it, the first variable name silently becomes `\ufeffSUPABASE_URL` and the app insists the variable
is missing.

The `Settings` class then fails loudly at startup if either credential is missing. Failing at
startup is deliberate: a broken config should not survive until the first request.

### `app/supabase_client.py` — one client, shared

```python
supabase: Client = create_client(settings.supabase_url, settings.supabase_key)
```

Creating one client at import time means every module talks to the same configured instance, instead
of building a new one per request.

### `app/schemas.py` — the shapes of requests and responses

```python
class Credentials(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
```

Those fields are optional **on purpose**. If they were required, FastAPI would reject a missing
field on its own with `422 Unprocessable Entity` — but the spec for this project requires `400`.
Making them optional lets the request reach our code, which returns the `400` itself.

### `app/dependencies.py` — the guard (the heart of the project)

Three pieces:

```python
bearer_scheme = HTTPBearer(bearerFormat="JWT", auto_error=False, ...)
```

Declaring this scheme is what makes the **Authorize** padlock appear in Swagger UI.
`auto_error=False` says: *don't* raise FastAPI's own error when the header is missing — hand us
`None` so we can return our own `{"error": "Access token required"}` instead of FastAPI's
`{"detail": "Not authenticated"}`.

```python
def verify_token(token): ...
```

Calls `supabase.auth.get_user(token)`. Three outcomes:

| Outcome | Response |
|---|---|
| Supabase says the token is good | returns the user |
| Supabase says no (expired, tampered, malformed) | `401 Invalid or expired token` |
| Supabase is unreachable (`AuthRetryableError`) | `503 Auth service unavailable` |

That last row matters. If Supabase is down, the caller's token might be perfectly fine — telling
them "invalid token" would send every client into a pointless re-login loop over an outage that is
not their fault.

```python
def require_auth(credentials = Depends(bearer_scheme)) -> AuthContext: ...
```

The guard itself. It rejects a missing/empty token, verifies the rest, and returns an `AuthContext`
holding **both** the user and the raw token string — logout needs the raw token, the profile route
only needs the user, so `get_current_user` unwraps it for routes that want the simpler thing.

Writing this once is the whole point of Stage 4. Adding a tenth protected route costs one line
(`Depends(get_current_user)`) and cannot forget a check.

### `app/routers/auth.py` — signup, login, logout

`_require_credentials()` is the shared 400-check for both signup and login.

Notice what login does **not** do:

```python
except AuthApiError:
    raise HTTPException(status_code=401, detail="Invalid login credentials")
```

Supabase's real message can distinguish "wrong password" from "no such user". Passing that through
would let an attacker discover which email addresses have accounts (*user enumeration*), so every
failure returns the same sentence.

Logout uses `supabase.auth.admin.sign_out(token, "global")` rather than `supabase.auth.sign_out()`.
The plain version signs out the SDK's *stored* session — but this server is stateless and never
stores one, so it would silently revoke nothing.

### `app/routers/public.py` and `protected.py`

The contrast is the lesson:

```python
def public_info():                              # no dependency: anyone
def profile(user=Depends(get_current_user)):    # guard runs first
```

By the time `profile()` starts executing, the token is already verified. The handler contains zero
auth logic.

### `app/main.py` — assembling everything

Creates the `FastAPI` app, wires the routers, and installs two error handlers that reshape FastAPI's
default `{"detail": ...}` into this project's `{"error": ...}`, and turn a malformed body into `400`
instead of `422`.

The `lifespan` function runs once at startup and prints the "connected to Supabase" line.

### `run.py` — the single start command

```bash
python run.py
```

Reads `PORT` from `.env` and starts Uvicorn with `reload=True`, so saving a file restarts the server
automatically.

---

## 4. The life of a request

**`GET /protected/profile` with a valid token**

```
1. Uvicorn receives the HTTP request
2. FastAPI matches the path to profile()
3. Before calling it: Depends(get_current_user) → Depends(require_auth)
4. HTTPBearer splits "Bearer eyJ..." and hands over the token
5. verify_token() calls Supabase: get_user(token)
6. Supabase confirms; the user record comes back
7. Only now does profile() run, and it just formats the user
8. 200 OK with id, email, created_at, ...
```

**Same request, no header**

```
3. require_auth receives credentials = None
4. raises HTTPException(401, "Access token required")
5. the error handler in main.py renders {"error": "Access token required"}
6. profile() never runs
```

That "never runs" is the security property worth internalising: the handler cannot leak data on a
bad token because it is never reached.

---

## 5. Status codes, and why each one

| Code | Meaning | Used here when |
|---|---|---|
| `200 OK` | Success, with a body | Login, profile, dashboard, public info |
| `201 Created` | Something now exists that didn't | Signup created a user |
| `204 No Content` | Success, deliberately empty | Logout — there is nothing to say |
| `400 Bad Request` | *Your* request was wrong | Missing email/password, malformed JSON |
| `401 Unauthorized` | Not authenticated (misnamed — it means "unauthenticated") | Missing, malformed, expired or invalid token; wrong password |
| `403 Forbidden` | Authenticated, but not allowed | Not used here — that's authorization |
| `503 Service Unavailable` | *We* are broken, try later | Supabase unreachable |

The distinction that trips people up: **400 vs 401**. If the request itself is malformed (no
password field at all), it is `400`. If the request is well-formed but the credentials or token are
not acceptable, it is `401`.

---

## 6. Talking to the API from the terminal

### On Windows PowerShell, type `curl.exe`

`curl` alone is an **alias for `Invoke-WebRequest`**, a different program that has no `-H` or `-d`.
That mismatch produces:

```
Invoke-WebRequest : Cannot bind parameter 'Headers'.
```

### Anatomy

```
curl.exe -i -X POST http://localhost:3000/auth/login -H "Content-Type: application/json" -d '{...}'
         │  │        │                                │                                   │
         │  │        │                                │                                   └ body
         │  │        │                                └ a header (repeat -H for more)
         │  │        └ the URL
         │  └ HTTP method (omit for GET)
         └ include the response headers and status line
```

### The quoting rule

PowerShell parses your line before curl sees it. Measured results for the same JSON body:

| What you type | What the server actually received |
|---|---|
| `-d "{\"email\":\"a@b.com\"}"` | `{\` ❌ |
| `-d '{"email":"a@b.com"}'` | `{email:a@b.com}` ❌ quotes stripped |
| `-d '{\"email\":\"a@b.com\"}'` | `{"email":"a@b.com"}` ✅ |
| `-d "@body.json"` (body in a file) | `{"email":"a@b.com"}` ✅ |

So: **single quotes outside, backslash before every inner quote.**

```
{"email":"you@example.com","password":"password123"}          ← the JSON you want
'{\"email\":\"you@example.com\",\"password\":\"password123\"}'  ← what you type
```

Headers are the opposite — use **double** quotes there so a `$variable` expands:

| You write | curl receives |
|---|---|
| `"Authorization: Bearer $t"` | `Authorization: Bearer eyJhbGci…` ✅ |
| `'Authorization: Bearer $t'` | `Authorization: Bearer $t` ❌ |

### Variables save your sanity

`$t = "value"` stores something; `$t` inside double quotes expands it. Log in and capture the token
in one line:

```powershell
$r = Invoke-RestMethod -Uri http://localhost:3000/auth/login -Method Post -ContentType "application/json" -Body '{"email":"you@example.com","password":"password123"}'; $t = $r.access_token
```

Then every protected call is just:

```powershell
curl.exe -i http://localhost:3000/protected/profile -H "Authorization: Bearer $t"
```

Variables live only in that terminal window. Open a new tab and `$t` is empty again — a common cause
of surprise `401`s.

---

## 7. Using Swagger UI

Open **http://localhost:3000/docs**. FastAPI builds this page from your code — every route, every
model, every status code you declared.

1. Expand `POST /auth/login` → **Try it out** → edit the body → **Execute**
2. Copy the `access_token` out of the response
3. Click the green **Authorize** button (top right)
4. Paste **just the token** — no `Bearer ` prefix; Swagger adds it
5. **Authorize** → **Close**. The open padlocks now show as closed
6. `GET /protected/profile` → **Try it out** → **Execute** → `200` with your user

The padlock only appears on routes whose dependency chain includes `HTTPBearer`. If a route you
expect to be protected has no padlock, it is not actually guarded — the padlock is a real signal,
not decoration.

---

## 8. Troubleshooting

**`Missing environment variable(s): SUPABASE_URL`**
No `.env`, wrong location, or a BOM at the start of the file. `config.py` handles the BOM; make sure
`.env` sits in the project root next to `run.py`.

**`Invalid API key` at startup**
The key is quoted in `.env` (`SUPABASE_KEY="eyJ..."`) or truncated. Store it bare, no quotes.
Also check you copied the **anon/publishable** key, not the project's JWT secret.

**`{"error":"email rate limit exceeded"}` on signup**
Supabase's free tier allows about 2 confirmation emails per hour on its shared SMTP. Turn off
**Authentication → Sign In / Providers → Email → Confirm email**, then signup sends no email at all.
To get a user immediately, create one in the dashboard: **Authentication → Users → Add user →
Create new user**, ticking **Auto Confirm User**.

**`401 Invalid login credentials` right after a successful signup**
The account exists but is unconfirmed. Same fix as above, or click the emailed link.

**`{"error":"Invalid request body"}`**
The shell mangled your JSON. See the quoting table in section 6.

**`curl: (3) URL rejected: Port number was not a decimal number`**
The command was split across lines when pasted, or `-X POST POST` left a stray word where the URL
should be.

**A tampered token still returns `200`**
Check *where* you changed a character. The signature is 64 bytes encoded as 86 base64url characters,
so the final character carries only 2 meaningful bits — the other 4 are padding the decoder throws
away. Changing `Q` to `X` there produces a byte-identical signature, so the token is not actually
modified. Change a character in the **middle** and it correctly returns `401`.

**Protected route still works after logout**
Expected. Sign-out revokes the *refresh* token; an already-issued access token stays valid until it
expires (up to an hour). Supabase documents this. Shorten the JWT expiry if it matters.

**Port 3000 already in use**
An older server is still running. Close that terminal, or change `PORT` in `.env`.

---

## 9. Git basics used here

```bash
git add -A                      # stage every change
git commit -m "message"         # save a snapshot with a description
git log --oneline               # list the snapshots
git push                        # send them to GitHub
```

`git -C "C:\path\to\repo" status` runs a command **as if** you were in that folder — handy when your
terminal is somewhere else. If you have already `cd`'d into the project, you never need `-C`.

The one rule that matters most: **`.env` must be in `.gitignore` before your first push.** Check
with

```bash
git ls-files
```

If `.env` appears in that list it is being tracked, and pushing would publish your keys. Untrack it
with `git rm --cached .env`, and treat any key that was pushed as compromised — rotate it in the
Supabase dashboard.

---

## 10. Ideas for going further

- **Refresh tokens** — add `POST /auth/refresh` so clients get a new access token without logging in
  again.
- **Roles** — add real *authorization*: an `/admin` route that checks a role claim, not just login.
- **Rate limiting** — cap login attempts per IP to blunt password guessing.
- **Tests** — `pytest` with FastAPI's `TestClient`, stubbing `supabase.auth.get_user` so tests run
  offline (that is exactly how each stage of this project was verified).
- **Deployment** — put it behind HTTPS. Bearer tokens over plain HTTP are readable by anyone on the
  network path.
