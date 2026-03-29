# Hetzner Server Provisioning Design

## Summary

Add a `pegasus server create` command that provisions a Hetzner Cloud server
configured for Kamal deployments. Uses sensible defaults with optional flag
overrides, auto-detects SSH keys, and optionally updates Kamal config if detected.

## Command Structure

```
pegasus server create <name>   # Provision a new Hetzner server
```

Future commands (not in v1): `server list`, `server destroy`.

## Detailed Flow

### 1. Hetzner API Token

**Resolution order** (same pattern as Pegasus API key):
1. `HETZNER_API_TOKEN` env var
2. `~/.pegasus/hetzner_credentials` file

If neither exists, print instructions for creating a token in the
Hetzner Cloud Console (https://console.hetzner.cloud → project → Security → API Tokens),
prompt for input, validate it with an API call, and save to `~/.pegasus/hetzner_credentials`
with 0o600 permissions.

### 2. SSH Key Detection

Scan `~/.ssh/` for `*.pub` files.

- **No keys found**: Print error explaining how to generate one (`ssh-keygen -t ed25519`),
  then exit with non-zero status. Do not create the server.
- **One key found**: Use it automatically.
- **Multiple keys found**: Prompt user to pick one.

Once a key is selected, check if it's already uploaded to Hetzner (match by public key content).
If not, upload it with a name derived from the filename (e.g. `id_ed25519`).

### 3. Server Creation

**Required argument:**
- `name` — server name (positional arg)

**Defaults with optional flag overrides:**

| Parameter | Default | Flag |
|-----------|---------|------|
| Server type | `cx22` (2 vCPU, 4GB, ~€4/mo) | `--server-type` |
| Image | `ubuntu-24.04` | `--image` |
| Location | `nbg1` (Nuremberg) | `--location` |

Create the server via hcloud SDK. Show a Rich spinner while waiting for
the server status to become `running`.

### 4. Output

Print:
- Server IP address
- SSH connection command: `ssh root@<ip>`
- Server name and type summary

### 5. Kamal Config Detection

Check if `config/deploy.yml` exists in the current directory.

- **If found**: Parse the YAML, find the `servers` → `web` section, and update
  the IP address. Show the user what changed.
- **If not found**: Print a note linking to Kamal deployment docs
  (https://docs.saaspegasus.com/deployment/kamal/).

## New Files

- `pegasus_cli/server.py` — `server` command group with `create` subcommand
- `pegasus_cli/hetzner_client.py` — Hetzner API wrapper using hcloud SDK
- `tests/test_server.py` — tests for the server command
- `tests/test_hetzner_client.py` — tests for the Hetzner client

## Modified Files

- `pegasus_cli/cli.py` — register `server` command group
- `pegasus_cli/credentials.py` — add Hetzner credential helpers
- `pyproject.toml` — add `hcloud` dependency, bump Python to >=3.10

## Dependencies

- Add `hcloud` as a regular dependency
- Bump `requires-python` from `>=3.9` to `>=3.10`

## Credential Management

Add to `credentials.py`:
- `HETZNER_CREDENTIALS_FILE = PEGASUS_DIR / "hetzner_credentials"`
- `get_hetzner_api_key()` — same pattern as `get_api_key()` but for Hetzner token
- `save_hetzner_api_key(key)` — same pattern as `save_api_key()`

## Error Handling

- Invalid/missing Hetzner token → prompt to enter one
- No SSH keys in ~/.ssh → error with ssh-keygen instructions, exit
- Server creation failure → display Hetzner API error message
- Network errors → display connection error
- Kamal config parse failure → skip config update, print manual instructions
