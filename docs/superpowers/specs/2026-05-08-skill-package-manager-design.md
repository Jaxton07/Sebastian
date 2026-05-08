---
version: "1.0"
last_updated: 2026-05-08
status: planned
integrated_to: capabilities/skill-package-manager.md
integrated_at: 2026-05-08
---

# Skill Package Manager Design

## 1. Background

Sebastian already supports Skill loading from builtin and user extension
directories, and v0.5.11 added new-session hot reload. That solves the runtime
side: a user can add or modify `SKILL.md` files under the configured Skill
roots and new sessions will see the updated prompt/tool snapshot without a
service restart.

The missing piece is distribution. Tools such as OpenClaw make community Skills
easy to discover and install from ClawHub. A user can search a registry,
install a versioned Skill bundle into a local workspace, and start a new
session. Sebastian should add that consumer workflow without turning every
third-party capability into a native internal tool.

## 2. External Research Summary

OpenClaw separates registry distribution from runtime capability execution:

- ClawHub is a public registry for versioned Skill bundles. A Skill bundle is a
  folder with `SKILL.md` plus optional support files.
- OpenClaw exposes native `openclaw skills search/install/update` for normal
  users.
- The separate `clawhub` CLI handles registry-authenticated flows such as
  publish, sync, delete, and owner management.
- ClawHub installs download a zip for a resolved Skill version, extract it into
  a local `skills/` directory, and write lock/origin metadata for later update.
- Updates compare local fingerprints to known registry versions and refuse to
  overwrite local changes unless forced.
- OpenClaw loads installed Skills on the next session and treats third-party
  Skills as untrusted content.

ClawHub-compatible registries support overriding the API endpoint with a CLI
flag or environment variable. Sebastian should follow that pattern instead of
hard-coding a mainland China mirror as default. The default registry is
`https://clawhub.ai`; users can point Sebastian at a mirror or self-hosted
compatible service when needed.

## 3. Goals

1. Add a Sebastian-native CLI for discovering and installing third-party Skills.
2. Install Skill bundles into Sebastian's existing user extension directory:
   `~/.sebastian/data/extensions/skills`.
3. Reuse the existing new-session Skill hot reload lifecycle. Installed Skills
   become available to new sessions, not the currently running turn.
4. Add a builtin `skill_installer` Skill that teaches Sebastian how to search,
   inspect, install, update, and remove Skills through the CLI.
5. Fix installer PATH ergonomics so `sebastian` is reliably available to users
   and to Sebastian's own Bash tool when running under systemd/launchd.
6. Keep internal tool surface small. Skill distribution is a CLI + builtin Skill
   workflow, not a growing list of native tools.

## 4. Non-Goals

- Do not implement Skill publishing or sync.
- Do not implement a graphical marketplace UI.
- Do not hot-refresh the current session after install.
- Do not execute third-party install scripts or dependency metadata in v1.
- Do not add a native model-visible `install_skill` tool.
- Do not support private registries requiring auth in v1.

## 5. User Experience

### CLI

```bash
sebastian skills search "flight"
sebastian skills inspect flight-search
sebastian skills install flight-search
sebastian skills list
sebastian skills update flight-search
sebastian skills update --all
sebastian skills remove flight-search
```

Every networked command accepts:

```bash
--registry https://clawhub.ai
```

The registry default resolves in this order:

1. `--registry`
2. `SEBASTIAN_SKILLS_REGISTRY_URL`
3. `https://clawhub.ai`

After a successful install or update, the CLI prints:

```text
Skill installed: skill__flight_search
Available to new Sebastian sessions. Existing sessions keep their current
Skill snapshot.
```

### Agent-Assisted Install

Sebastian gets a builtin Skill named `skill_installer`.

It instructs the agent to:

1. Search with `~/.sebastian/bin/sebastian skills search ...`.
2. Inspect a candidate before installing.
3. Summarize source, version, file list, declared metadata, and any warnings.
4. Ask the user for confirmation before install/update/remove.
5. Run the CLI through Bash after approval.
6. Tell the user that the Skill becomes available in a new session.

The Skill must explicitly forbid:

- Running unknown scripts from downloaded Skill bundles.
- Using `curl | bash` style install flows for third-party Skills.
- Installing from a registry other than the default unless the user requested
  that registry.

## 6. Architecture

### New Modules

```text
sebastian/cli/skills.py
sebastian/cli/path_setup.py
sebastian/capabilities/skills/skill_installer/SKILL.md
sebastian/capabilities/skills/metadata.py
sebastian/skills_registry/
  __init__.py
  client.py
  installer.py
  lockfile.py
  models.py
  safety.py
```

`sebastian/main.py` mounts `skills.py` as:

```python
app.add_typer(skills_app, name="skills")
```

The split keeps `sebastian/main.py` small and makes registry behavior testable
without invoking Typer.

### Data Paths

Installed Skills live under:

```text
<settings.skills_extensions_dir>/<slug>/
  SKILL.md
  ...
```

Managed metadata lives under:

```text
<settings.skills_extensions_dir>/.sebastian-skills.lock.json
<settings.skills_extensions_dir>/<slug>/.sebastian-origin.json
```

The lockfile tracks:

```json
{
  "version": 1,
  "skills": {
    "flight-search": {
      "slug": "flight-search",
      "registered_name": "skill__flight_search",
      "registry": "https://clawhub.ai",
      "version": "1.2.3",
      "tag": "latest",
      "sha256": "...",
      "fingerprint": "...",
      "installed_at": "2026-05-08T12:00:00Z"
    }
  }
}
```

The per-Skill origin file duplicates the entry for easier inspection and
recovery if the central lockfile is damaged.

Lockfile updates must be concurrency-safe:

- All lockfile read-modify-write operations acquire an exclusive file lock.
- Writes go to a temp file in the same directory, flush, fsync, then atomic
  replace the lockfile.
- Directory replacement and lockfile replacement are treated as a two-step
  transaction. If lockfile writing fails after the Skill directory is replaced,
  restore the previous directory backup and leave the old lockfile intact.
- Per-Skill `.sebastian-origin.json` uses the same temp-file + fsync + atomic
  replace rule.

## 7. Registry Client

Sebastian implements a ClawHub-compatible HTTP client rather than shelling out
to the npm `clawhub` CLI. Reasons:

- Sebastian stays Python-only for install/update flows.
- Error messages and lockfile semantics can match Sebastian's UX.
- Safety checks can run before extraction.
- The agent can use one stable `sebastian skills` command.

Expected endpoints:

- `GET /api/v1/search?q=<query>&limit=<n>`
- `GET /api/v1/skills/<slug>`
- `GET /api/v1/download?...`

HTTP should rely on standard proxy environment variables:

- `HTTPS_PROXY`
- `HTTP_PROXY`
- `NO_PROXY`

The client should be tolerant of small response shape differences by parsing
only the fields Sebastian needs:

- slug
- name
- summary/description
- latest version
- version list when available
- file list when available
- download URL or downloadable endpoint
- sha256/digest when available
- moderation/security status when available

If the registry does not expose a digest, Sebastian still computes the local
zip SHA256 and records it, but the CLI warns that no registry digest was
available for pre-download verification.

Download URLs are constrained:

- The registry URL must be HTTPS unless a local development flag is added in
  tests only.
- Prefer the same-origin registry endpoint (`/api/v1/download...`) over
  arbitrary URLs embedded in registry metadata.
- If metadata returns a direct download URL, accept it only when it is HTTPS and
  either same-origin with the registry or explicitly allowed by a future
  registry trust policy. V1 should not follow arbitrary third-party download
  origins by default.

Security and moderation states are fail-closed. If a registry marks a Skill or
version as `malicious`, `quarantined`, `blocked`, `hidden`, `suspicious`, or an
equivalent unsafe state, install/update refuses by default and `inspect`
displays the status and reason. Agent-assisted installs must not use `--force`
to bypass unsafe status. Whether a manual CLI `--force` can bypass suspicious
but non-malicious states is left for implementation review; it must never be
available through `skill_installer`.

## 8. Install Flow

`sebastian skills install <slug>`:

1. Resolve registry URL.
2. Resolve Skill version (`--version` or latest/tag).
3. Download archive to a temp directory.
4. Verify registry-provided SHA256 if present.
5. Inspect archive safety before extraction.
6. Extract into a temp staging directory.
7. Validate staging root:
   - exactly one Skill root, or root directly contains `SKILL.md`
   - root-level `SKILL.md` exists
   - parsed Skill name is valid
   - registered name does not collide with native/MCP reserved names
   - registered name does not collide with an existing Skill, unless this is an
     update or forced reinstall of the same managed slug
   - registry moderation/security status is installable
8. If destination exists:
   - refuse by default
   - allow overwrite with `--force` only if user explicitly requests it
9. Perform a recoverable directory swap:
   - write extracted content to a temp sibling directory
   - move existing destination to a backup sibling if it exists
   - move staging directory into the destination path
   - preserve backup until lockfile/origin writes succeed
   - roll back by removing the new destination and moving backup back on failure
10. Compute installed fingerprint and write lock/origin metadata.
11. Print new-session availability message.

`inspect` never writes files. If the registry exposes raw files or file lists,
`inspect` displays `SKILL.md` metadata, version, files, and warnings. If the
registry only exposes archive download, `inspect` may download into a temp
directory, run the same safety scan, and discard the archive.

## 9. Update and Remove

### Update

`sebastian skills update <slug>`:

1. Load lockfile entry.
2. Compute local fingerprint.
3. If local fingerprint differs from lockfile:
   - refuse by default
   - allow with `--force`
4. Resolve latest or requested version.
5. If already installed version is current and not forced, no-op.
6. Reuse install flow into a staging directory.
7. Compare the staged frontmatter registered name with the lockfile entry.
   If it changes, refuse by default because this changes the runtime tool name.
   Interactive manual update may allow the rename after explicit confirmation;
   `skill_installer` must not auto-accept renames.
8. Replace destination and update lockfile.

`sebastian skills update --all` loops lockfile entries and applies the same
rules. A single failed update should not stop unrelated entries; the command
returns non-zero if any entry failed and prints a summary.

### Remove

`sebastian skills remove <slug>`:

1. Resolve installed directory from lockfile or slug.
2. Confirm in interactive mode unless `--yes` is set.
3. Remove the directory.
4. Remove lockfile entry.
5. Print that new sessions will no longer see the Skill.

Manual Skills without lockfile entries can be removed only with an explicit
path or `--unmanaged` flag. V1 may omit unmanaged removal if it complicates the
interface.

## 10. Safety Rules

Archives are untrusted. Sebastian must reject:

- absolute paths
- `..` traversal
- symlink or hardlink entries
- device files, fifos, sockets
- files whose resolved path escapes the staging root
- more than 200 files
- any single file larger than 1 MiB
- total extracted size larger than 5 MiB
- missing `SKILL.md`
- binary `SKILL.md`
- invalid frontmatter name

Name normalization:

- registry slug uses the registry-provided slug
- Skill registered name is still `skill__<frontmatter name>`
- allowed characters for frontmatter name: `A-Za-z0-9_-`
- display warnings if slug and frontmatter name normalize differently
- registered name collisions are rejected unless the destination belongs to the
  same managed slug being updated or force-reinstalled

Skill metadata parsing and validation must be shared with runtime loading.
Current runtime loading parses frontmatter directly in `_loader.py`; v1 should
extract a shared helper such as:

```python
parse_skill_metadata(content: str, fallback_name: str) -> SkillMetadata
validate_skill_name(name: str) -> None
```

The installer, `_loader.py`, and hot reload path should all use that helper so
CLI-installed Skills and manually added Skills follow the same name rules.
Invalid manual Skills should be skipped with a clear warning rather than being
registered as malformed tool names.

Package-manager fingerprints must exclude Sebastian management metadata,
including:

- `<skill>/.sebastian-origin.json`
- `<skill>/.sebastian/`
- any future manager-owned metadata paths documented by `lockfile.py`

Otherwise writing origin metadata would immediately change the fingerprint and
make the next update look like a local user modification.

Sebastian does not execute installer metadata, dependency hints, or scripts in
v1. A Skill can include scripts, but they are just files. The agent may later
run them through Bash only after normal permission review and user approval.

## 11. PATH Setup

Current installer behavior activates `.venv` only inside `scripts/install.sh`.
After installation, users and service-managed Bash commands may not have
`sebastian` on `PATH`.

V1 adds a stable shim:

```text
~/.sebastian/bin/sebastian
```

The shim is an executable script:

```sh
#!/usr/bin/env sh
exec "$HOME/.sebastian/app/.venv/bin/sebastian" "$@"
```

If `SEBASTIAN_INSTALL_DIR` is custom, the shim should point at that resolved
install dir instead of assuming `~/.sebastian/app`.

The shim path itself remains fixed at `~/.sebastian/bin/sebastian` for the
default user install. `SEBASTIAN_SKIP_PATH_SETUP=1` skips shell rc modification
only; it does not skip shim creation or refresh. `skill_installer` is designed
for installed Sebastian deployments and does not guarantee that a source-tree
development checkout has this shim.

`scripts/install.sh` should:

1. Create or update the shim.
2. Export `PATH="$HOME/.sebastian/bin:$PATH"` for the current install process.
3. Unless `SEBASTIAN_SKIP_PATH_SETUP=1`, add a managed PATH block to shell rc
   files by default.

Existing users who upgrade through `sebastian update` do not run
`scripts/install.sh`, so updater must also call the same `path_setup.py` helper
after a successful dependency reinstall and before service restart. This keeps
`~/.sebastian/bin/sebastian` available for v0.5.11-and-earlier installs after
their first upgrade to the Skill package manager release. The update path should
refresh the shim and print the same shell rc guidance, while preserving
`SEBASTIAN_SKIP_PATH_SETUP=1`.

Managed block:

```sh
# >>> sebastian PATH >>>
export PATH="$HOME/.sebastian/bin:$PATH"
# <<< sebastian PATH <<<
```

Shell rc targets:

- zsh: `~/.zshrc`
- bash on Linux: `~/.bashrc`
- bash on macOS: `~/.bash_profile` and `~/.bashrc` when they exist; if neither
  exists, create `~/.bash_profile`

The block writer must be idempotent:

- update existing Sebastian block
- never append duplicates
- preserve other user content

Unsupported shells should not be modified automatically. The installer prints a
manual instruction instead.

The builtin `skill_installer` Skill uses the shim path explicitly:

```bash
~/.sebastian/bin/sebastian skills search ...
```

That avoids relying on systemd/launchd service `PATH`.

## 12. Interaction With Hot Reload

No new runtime reload channel is needed in v1.

- Gateway startup loads builtin Skills and user extension Skills.
- New-session first turns check `SKILL.md` fingerprints.
- Installed or removed Skills change `SKILL.md` presence under
  `settings.skills_extensions_dir`.
- Existing sessions keep their captured prompt/tool snapshot.
- New sessions see the updated Skill set.

This matches the existing v0.5.11 consistency model and avoids introducing
CLI-to-gateway auth or IPC.

## 13. Permissions

No new model-visible native tool is added.

The agent uses the existing `Bash` tool, which is `MODEL_DECIDES`. That means
commands go through `PermissionReviewer`, but it does not guarantee a user
approval prompt: the reviewer may return `proceed`. The safety boundary cannot
depend only on prompt wording.

`skill_installer` must therefore state hard operating rules:

- Do not run `install`, `update`, or `remove` until the user explicitly
  authorizes that action in the current conversation.
- Do not pass `--yes` or `--force` unless the user explicitly requested that
  flag in the current conversation.
- Do not use `--force` to bypass unsafe registry moderation/security states.
- Do not auto-accept update-time registered name changes.
- Do not use a non-default `--registry` unless the user named that registry.

CLI commands themselves are local user actions. Interactive CLI install/update
should ask for confirmation when overwriting, removing, or using a non-default
registry. Non-interactive flags must be explicit (`--yes`, `--force`,
`--registry`).

## 14. Documentation Updates

Update:

- `README.md`: mention `sebastian skills` and PATH shim behavior.
- `sebastian/README.md`: CLI and capabilities overview.
- `sebastian/cli/README.md`: new `skills` subcommand and PATH setup helper.
- `sebastian/capabilities/README.md`: Skill install workflow.
- `sebastian/capabilities/skills/README.md`: installed Skills lifecycle and
  `skill_installer`.
- `sebastian/config/README.md`: mention `skills_extensions_dir` if needed.
- `docs/architecture/spec/capabilities/`: integrate the implemented design into
  the architecture spec tree when implementation lands.
- `docs/architecture/spec/capabilities/INDEX.md`: link the integrated Skill
  package manager spec.
- `CHANGELOG.md`: user-facing Added/Changed entries when implementation lands.

## 15. Testing Plan

### Unit

- registry URL resolution order
- search/inspect response parsing
- archive safety rejects traversal, symlinks, absolute paths, oversized files
- install validates `SKILL.md`
- install writes lockfile and origin metadata
- update refuses local fingerprint mismatch unless forced
- remove updates lockfile
- PATH block writer is idempotent for zsh/bash rc files
- shim generation respects custom install dir
- updater refreshes shim for existing installs after successful update
- shared Skill metadata validation is used by both installer and runtime loader
- unsafe registry security/moderation states fail closed
- lockfile updates use exclusive locking and atomic writes
- download URL policy rejects non-HTTPS and arbitrary third-party origins
- registered name collision rejects installing a different slug over an
  existing Skill
- package-manager fingerprint ignores `.sebastian-origin.json` and manager
  metadata directories
- update-time frontmatter registered name changes require explicit manual
  confirmation and are forbidden for agent-assisted automatic update
- recoverable directory swap rolls back on lockfile/origin write failure

### CLI

Use Typer `CliRunner` with mocked registry client:

- `skills search`
- `skills inspect`
- `skills install`
- `skills list`
- `skills update`
- `skills remove`

### Integration

- Install a fixture Skill into a temp `settings.skills_extensions_dir`.
- Trigger `SkillHotReloader.maybe_reload()`.
- Assert registry exposes `skill__<name>` to new prompt/tool snapshots.

### Installer Script

Shell-level tests should cover:

- shim creation
- existing managed block update
- skip via `SEBASTIAN_SKIP_PATH_SETUP=1`
- non-default `SEBASTIAN_INSTALL_DIR`

## 16. Rollout

This should ship as a minor feature release. It is additive and does not change
existing Skill loading behavior.

Recommended implementation phases:

1. PATH shim and shell rc setup.
2. Registry models/client/safety/lockfile.
3. CLI subcommands.
4. Builtin `skill_installer`.
5. Documentation and CHANGELOG.

## 17. Open Questions

1. Should `inspect` require a registry file-list endpoint, or may it download
   the archive to a temp directory when file listing is unavailable?
   Recommendation: allow temp download; reuse safety scanner and avoid blocking
   compatible registries with smaller APIs.
2. Should unmanaged local Skills appear in `sebastian skills list`?
   Recommendation: yes, mark them as `unmanaged` if they have `SKILL.md` but no
   lockfile entry.
3. Should install support direct GitHub URLs?
   Recommendation: not in v1. Keep the first release registry-only.
