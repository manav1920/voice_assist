# Manasvi — Authentication Setup

This adds real accounts to Manasvi: email/password signup with email
verification, login, "Continue with Google," and password reset —
using **Supabase for auth only**. Your **MySQL database stays the
source of truth** for `users`, `conversations`, `messages`, and
`memory`.

---

## What was built

**Backend**
- `app/auth.py` *(new)* — verifies Supabase JWTs and resolves the
  matching MySQL user.
- `app/database.py` *(rewritten)* — now uses a connection **pool**
  instead of one shared connection (the old version wasn't safe once
  multiple people can be logged in and hitting the API at the same
  time), plus `get_user_by_supabase_id`, `create_user`,
  `update_last_login`.
- `app/server.py` *(updated)*:
  - `GET /api/public-config` — hands the frontend the Supabase URL +
    anon key (both are meant to be public; see note below).
  - `POST /api/auth/sync` — verifies the JWT and creates-or-updates
    the MySQL row, stamping `last_login`.
  - `GET /api/auth/me` — returns the current user's MySQL row.
  - `/api/converse`, `/api/history`, `/api/reset` now **require**
    a valid Supabase Bearer token.
  - Conversation history is now **per user** (previously it was one
    global conversation shared by anyone who used the app).
- `app/api.py` — **removed**. It was a second, disconnected FastAPI
  app with a `/users/count` endpoint that called methods no longer on
  `DatabaseManager`. Its purpose is superseded by the endpoints above.
- `voice_assist_sql.sql` — added `profile_picture` and
  `onboarding_completed` columns to `users` (an `ALTER TABLE` version
  is included as a comment if you already have data in that table).

**Frontend**
- `static/auth.html` *(new)* — the login/signup page: two cards
  (animated switch), Google button, forgot-password flow, inline
  validation, loading states, and a password-reset landing state —
  styled to match Manasvi's existing dark glass look rather than a
  generic template.
- `static/index.html` *(updated)* — now checks for a session on load
  and redirects to `auth.html` if you're not logged in; shows your
  name and a **Log out** button; sends your session token with every
  API call; and (bonus fix) now actually persists your conversation
  across page refreshes, scoped per account.

---

## 1. Create a Supabase project

1. Go to [supabase.com](https://supabase.com) → **New project**.
2. Pick a name, a database password (you won't need this password —
   we're not using Supabase's database), and a region close to you.
3. Wait for provisioning (~2 minutes).

### Get your keys

Go to **Project Settings → API**. You need:

| Value | Where | Goes in `.env` as |
|---|---|---|
| Project URL | "Project URL" | `SUPABASE_URL` |
| anon public key | "Project API keys" → `anon` `public` | `SUPABASE_ANON_KEY` |
| JWT Secret | scroll down to "JWT Settings" → `JWT Secret` | `SUPABASE_JWT_SECRET` |

> **Note on the JWT Secret**: some newer Supabase projects default to
> asymmetric (RS256/ES256) signing keys instead of the legacy shared
> secret. If you don't see a "JWT Secret" field, look for **JWT Keys**
> and switch to (or add) a **Legacy HS256 shared secret** — that's
> what `app/auth.py` verifies against in this build. If you'd rather
> use the newer asymmetric keys, say so and I'll switch `auth.py` to
> verify against Supabase's public JWKS endpoint instead.

### Enable email confirmations

**Authentication → Providers → Email** — make sure "Confirm email" is
turned on (it usually is by default). This is what makes Supabase
send the verification link after signup.

### Set your Site URL and redirect URLs

**Authentication → URL Configuration**:
- **Site URL**: `http://localhost:8000`
- **Redirect URLs**: add `http://localhost:8000/auth.html`

(Update these to your real domain later when you deploy.)

---

## 2. Enable Google login

1. **Authentication → Providers → Google** in Supabase → toggle it on.
2. You'll need a Google OAuth Client ID + Secret from
   [Google Cloud Console](https://console.cloud.google.com/):
   - **APIs & Services → Credentials → Create Credentials → OAuth
     client ID** → Application type: **Web application**.
   - Under **Authorized redirect URIs**, add the callback URL Supabase
     shows you on that same Providers → Google screen — it looks like:
     `https://<your-project-ref>.supabase.co/auth/v1/callback`
3. Paste the Client ID and Client Secret into Supabase's Google
   provider settings and save.

That's it — no Google-specific code is needed on your end; Supabase
handles the OAuth handshake, and `auth.html` already calls
`signInWithOAuth({ provider: 'google' })`.

---

## 3. Set up MySQL

If you don't already have MySQL running:

- **Windows**: install [MySQL Community Server](https://dev.mysql.com/downloads/mysql/), or use XAMPP/WAMP.
- **Mac**: `brew install mysql && brew services start mysql`
- **Linux**: `sudo apt install mysql-server`

Then create the database and run the schema:

```bash
mysql -u root -p
```
```sql
CREATE DATABASE manasvi;
USE manasvi;
SOURCE /path/to/voice_assist/voice_assist_sql.sql;
```

(If you already ran the old version of this file and have real rows
in `users`, don't re-run the `CREATE TABLE` — use the `ALTER TABLE`
statement included as a comment near the top of the file instead.)

---

## 4. Add these to your `.env`

```
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your-anon-public-key
SUPABASE_JWT_SECRET=your-jwt-secret

DB_HOST=localhost
DB_PORT=3306
DB_NAME=manasvi
DB_USER=root
DB_PASSWORD=your-mysql-password
```

(`DB_*` may already be set from your earlier work — just confirm they
match a real, running MySQL instance.)

---

## 5. Install the new dependencies and run it

```bash
pip install -r requirements-server.txt
uvicorn app.server:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** — you'll now land on the login page
first. Sign up, check your email for the verification link, click it,
log back in, and you'll land on the assistant with your name shown in
the header.

---

## Notes / things worth knowing

- **The anon key is safe to expose to the browser.** That's how
  Supabase is designed — it has no special privileges by itself; your
  actual protection is that `app/auth.py` verifies every JWT
  server-side before trusting it. The **JWT Secret** and any MySQL
  credentials are never sent to the browser.
- **`/dashboard`**: your brief says redirect to `/dashboard` after
  login. Since there's no separate dashboard yet, `auth.html` redirects
  to `index.html` (the assistant itself) — tell me when you're ready
  to build a real dashboard/onboarding step and I'll wire the redirect
  there instead.
- **Conversation history** is now per-user in memory (resets if the
  server restarts) and the *browser-side* transcript view is per-user
  in `localStorage`. Nothing about `conversations`/`messages`/`memory`
  tables is wired up yet — those exist in your schema but the pipeline
  doesn't write to them. Want me to persist actual conversations to
  MySQL next, instead of just in-memory?
