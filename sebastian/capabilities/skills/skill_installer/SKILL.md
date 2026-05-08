---
name: skill_installer
description: Search, inspect, install, update, list, and remove Sebastian Skills through the Sebastian CLI.
---

Use this Skill when the user asks to find, install, update, list, or remove Sebastian Skills.

Use the public Sebastian CLI command from PATH. Do not call installation-specific
shim paths directly:

```bash
sebastian skills search "<query>"
sebastian skills inspect <slug>
sebastian skills install <slug>
sebastian skills list
sebastian skills update <slug>
sebastian skills remove <slug>
```

Rules:

- Always inspect before install or update.
- Before install or update, summarize registry-visible metadata: registry, slug/name, version, security/moderation status, download URL/SHA if shown, and warnings.
- Do not require a bundle file summary; CLI inspect does not list files unless future registry metadata provides them.
- After install or update, report the registered runtime Skill name from the CLI output.
- Ask the user for explicit confirmation before install, update, or remove.
- Do not pass `--yes` or `--force` unless the user explicitly requested that flag in the current conversation.
- Do not pass `--allow-rename` unless the user explicitly approves the registered-name change in the current conversation.
- Never use `--force` to bypass unsafe registry security/moderation status.
- Do not auto-accept an update that changes the registered Skill name.
- Do not use `--registry` unless the user names that registry.
- Never run scripts from downloaded Skill bundles during install.
- Never use `curl | bash` or similar third-party install commands.
- After install, update, or remove, tell the user the change applies to new Sebastian sessions.
