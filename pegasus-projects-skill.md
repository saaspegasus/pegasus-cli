---
name: pegasus-projects
description: |
  Use when the user asks to create, view, or modify a SaaS Pegasus project
  via the `pegasus` CLI — e.g. "create a new Pegasus project for X",
  "add subscriptions to my Pegasus project", "show me my project settings",
  "switch the front-end framework to React", "what features can I use on
  my license tier". This skill covers the `pegasus projects create / update /
  show / fields` commands and the underlying API shape.
---

# Managing SaaS Pegasus projects

You are managing a SaaS Pegasus project on behalf of the user. Pegasus is a
Django boilerplate; a "project" is a configuration of features (frontend
framework, auth providers, billing, AI, etc.) that the Pegasus build pipeline
later renders into a real Django codebase. Your job is to translate the user's
intent into the right CLI calls.

## Setup (one time)

Authentication uses an API key from saaspegasus.com.

- Check if `pegasus auth` is already configured: a key lives at
  `~/.pegasus/credentials`, or in `$PEGASUS_API_KEY`.
- If not, ask the user to run `pegasus auth` themselves. Don't try to guess
  or generate a key — they must paste their own.
- Base URL defaults to `https://www.saaspegasus.com`. For local development
  override with `PEGASUS_BASE_URL=http://localhost:8000`.

## Commands

```
pegasus projects list                       # list all projects
pegasus projects fields --json              # field catalog + your tier (parse this)
pegasus projects show <id> --json           # full config of one project
pegasus projects create --json [--set k=v ...] [--config-file path]
pegasus projects update <id> --json [--set k=v ...] [--config-file path]
pegasus projects push <id>                  # push to GitHub (separate flow)
```

**ALWAYS pass `--json` when you (an agent) are inspecting output.** The
default is a Rich table for humans that may truncate or scroll past your
visible viewport — a 60+ field schema looks like fields are missing when
they aren't. JSON output is always complete and parseable. Treat tables as
human-only.

## The standard workflow

For any non-trivial create or update, work in this order:

1. **Call `pegasus projects fields --json`** to get the schema. It returns:
   ```json
   {
     "user_tier": "free" | "basic" | "pro" | "unlimited",
     "fields": {
       "project_name":      { "type": "string", "max_length": 100 },
       "use_celery":        { "type": "boolean", "min_tier": "free" },
       "use_subscriptions": { "type": "boolean", "min_tier": "pro" },
       "ai_chat_mode":      { "type": "choice", "choices": ["openai", "llm", "none"], "min_tier": "pro" },
       ...
     }
   }
   ```
   The full response has ~60+ fields. If your parsing gives you fewer than
   ~50, you're probably reading truncated output — re-run with `--json` and
   parse the raw JSON.

   - `min_tier` only appears on fields gated by a license tier. Compute
     "can I use this?" client-side: `field.min_tier <= user_tier` per the
     ordering `free < basic < pro < unlimited`. No feature requires
     `unlimited` today — treat unlimited as ≥ pro for the math.
   - Fields without `min_tier` (project_name, project_slug, css_framework,
     bundler, etc.) are tier-agnostic.

2. **If the user asked for a tier-gated feature they can't use**, surface
   that *before* attempting the call. Say something like: "Subscriptions
   requires a Pro license; you're on free tier. Want to skip it, or upgrade?"

3. **Construct the payload.** Two ways to provide settings, combinable:
   - `--set key=value` (repeatable) for individual fields. Booleans accept
     `true`/`false`/`yes`/`no`/`y`/`n`. `null`/`none`/empty for None.
   - `--config-file path` to load a YAML or JSON file. If the file has a
     `default_context:` top-level key (real `pegasus-config.yaml` shape),
     it's unwrapped automatically. `--set` values override file values.

4. **Call create or update.** The response is the full project in
   `pegasus-config.yaml` shape (see "The config shape" below).

5. **On a 400**, read the response body. Errors are keyed by field. Example:
   ```json
   { "use_subscriptions": ["Subscriptions is not available on your current license..."] }
   ```
   Adjust and retry, or report to the user.

## The config shape

The API speaks the same key shape as a project's local `pegasus-config.yaml`,
with a few specifics:

- **JSON booleans on output**, but input also accepts `"y"`/`"n"` strings —
  so an agent can paste yaml back without translating.
- **Required on create**: only `project_name` and `project_slug`. Everything
  else uses model defaults. `author_name`, `email`, and `license` auto-populate
  from the user's profile if omitted.
- **`project_slug`** must be a valid Python identifier, lowercase, no leading
  or trailing underscore, and not a reserved name (`apps`, `templates`,
  `pegasus`, stdlib module names, etc.). Server normalizes/validates.
- **Renamed wire keys** (different from the model field name):
  - `project_name` ↔ model `name`
  - `use_auto_reload` ↔ model `use_browser_reload`
- **`pegasus_version`** is the *pinned* version (a string like `"2026.5.0"`)
  or `null` to track latest. Output also includes `_pegasus_version`
  (read-only, the resolved version that would be used at build time).
- **`css_framework`** is one of `"tailwind"`, `"bootstrap"`,
  `"bootstrap-material"`, `"bulma"`. **Default to `tailwind` without
  asking** — the others are actively being phased out and shouldn't be
  recommended for new projects. Only pick something else if the user
  explicitly asks for it. `css_theme` is a read-only output field derived
  from `css_framework`.
- **`license`** is a UUID string. Pass `null` for free tier. Must belong to
  the requesting user.

### Read-only fields (output only, ignored on input)

- `id`
- `_pegasus_version` (resolved version)
- `github_username` (computed from the linked GitHub repo or user profile)
- `css_theme` (computed from `css_framework`)

You can safely PATCH the entire GET response back — read-only keys are
silently dropped.

## License × feature gating

License tiers (low to high): `free`, `basic`, `pro`, `unlimited`.

The server validates feature compatibility at create/update time and again
at build time. If a project has features its license can't support, the
API rejects with a 400 keyed per offending feature.

You should pre-check via the schema's `min_tier` rather than discovering
through 400s. If the user wants something their tier can't do:

- If a license upgrade unblocks them, surface that as an option.
- If they want to drop the gated features instead, propose the specific
  subset to remove.

If the user has no license at all and the free tier flag is active for them,
their tier is `free`. Otherwise no license means they can't build at all
(the API will create projects but `pegasus push` will refuse).

## Common patterns

**"Create a project for me with X, Y, Z":**
1. Get schema → check user_tier supports X, Y, Z.
2. If anything's gated, tell the user and confirm before proceeding.
3. `pegasus projects create --json --set project_name="..." --set project_slug=... [--set k=v ...]`
4. Show the resulting project to confirm.

**"Show me my project / what's in it":**
- `pegasus projects show <id> --json` and present relevant subset to user.

**"Add feature X" / "switch to React" / etc:**
1. `pegasus projects show <id> --json` to see current state.
2. Confirm the field exists and the user's tier supports it
   (`pegasus projects fields --json`).
3. `pegasus projects update <id> --json --set key=value`.

**"Apply these settings from this yaml file":**
- `pegasus projects update <id> --json --config-file path/to/pegasus-config.yaml`.
- Combine with `--set` to override specific values.

**"What can I configure?" / "What features are available?":**
- `pegasus projects fields --json` and parse it. Don't rely on the table.

## Gotchas

- **Always parse JSON, never the table.** Repeating because it bites:
  `pegasus projects fields` without `--json` is a Rich table that can be
  truncated by terminal height. If you think the schema is "missing" a
  field, you're almost certainly reading truncated output — re-run with
  `--json`.
- **Slug uniqueness is per-user.** Two users can both have a project with
  slug `my_app`. You can't have two on one account.
- **PATCH is partial.** Unspecified fields stay as-is. To "reset" a field,
  you must explicitly set it (e.g., `--set ai_chat_mode=none`).
- **Pegasus version is finicky.** Pinned version (`"2026.5.0"`) or null. If
  the user wants the latest, use null — don't try to discover the latest
  version string yourself.
- **License downgrade can break a project.** If the user PATCHes to a lower
  license tier while pro features are on, the API will 400. Either remove
  the pro features in the same PATCH or do it as two steps.
- **Don't try to discover available choices.** The schema endpoint lists
  every choice for every choice-typed field. Use it.
- **Pegasus build is a separate step.** Creating/updating a project doesn't
  generate any code — that happens via `pegasus projects push` (creates a
  GitHub PR with the rendered project). Build-time validation is stricter
  than create-time validation; if it passes the API it might still fail at
  build with a license/feature/release combo issue.

## Output for the user

Pegasus CLI commands print Rich tables by default. When you're acting as an
agent for a human:

- Show meaningful state changes (the project's new name, the feature you
  changed, etc.), not the entire 60-field config dump.
- Surface license/tier issues clearly — these are conversion moments where
  the user might want to upgrade.
- For multi-step flows (check tier → propose payload → confirm → execute),
  pause at each step rather than running blind.
