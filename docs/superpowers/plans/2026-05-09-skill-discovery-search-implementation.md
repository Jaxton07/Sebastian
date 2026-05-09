# Skill Discovery Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Sebastian prefer local Skill discovery for reusable domain tasks and make `sebastian skills search` handle multilingual, multi-token local queries deterministically.

**Architecture:** Keep progressive disclosure intact: Skills remain local catalog packages, not provider tools. The model expands user intent into a multilingual search query in the fixed Skill bootstrap, while the CLI performs deterministic offline multi-token scoring across local Skill metadata. No keywords, aliases, package mutation, embeddings, or automatic top-k prompt injection.

**Tech Stack:** Python 3.12, Typer CLI, pytest, Sebastian local Skill package manager.

---

## Current Worktree Note

Before executing this plan, preserve unrelated existing uncommitted changes:

- `docs/superpowers/specs/2026-05-08-skill-package-manager-design.md`
- `sebastian/capabilities/skills/skill_manager/SKILL.md`
- `sebastian/cli/skills.py`
- `tests/unit/runtime/test_skills_cli.py`

Those files may already contain the separate "install/update available immediately" wording change. Do not revert or overwrite it. If a task below touches the same files, edit around the existing content.

## File Structure

- Modify `sebastian/skills_registry/models.py`
  - Add an optional `name` field to `InstalledSkill` so local search can use frontmatter `name` explicitly.
- Modify `sebastian/skills_registry/installer.py`
  - Populate `InstalledSkill.name` from parsed local `SKILL.md` metadata for builtin, managed, and unmanaged Skills.
- Modify `sebastian/cli/skills.py`
  - Replace literal full-query substring search with tokenized OR matching and deterministic scoring.
- Modify `sebastian/core/base_agent.py`
  - Strengthen the fixed `## Skill Management` bootstrap with local discovery policy and multilingual query examples.
- Modify `tests/unit/runtime/test_skills_cli.py`
  - Add CLI search tests for multi-token OR matching, name matching, scoring order, and whitespace query behavior.
- Modify `tests/unit/skills_registry/test_installer.py`
  - Assert `list_installed()` exposes frontmatter `name`.
- Modify `tests/unit/core/test_prompt_builder.py`
  - Assert the prompt includes domain-first Skill discovery and Chinese + English query examples.
- Update docs:
  - `docs/superpowers/specs/2026-05-08-skill-progressive-disclosure-design.md`
  - `docs/architecture/spec/core/system-prompt.md`
  - `docs/architecture/spec/capabilities/skill-package-manager.md`
  - `sebastian/capabilities/skills/README.md`
  - `sebastian/cli/README.md`

## Task 1: Expose Frontmatter Name On InstalledSkill

**Files:**
- Modify: `sebastian/skills_registry/models.py`
- Modify: `sebastian/skills_registry/installer.py`
- Test: `tests/unit/skills_registry/test_installer.py`

- [ ] **Step 1: Write the failing test**

In `tests/unit/skills_registry/test_installer.py`, extend `test_list_installed_merges_managed_and_unmanaged_skills()` so it asserts each listed Skill carries the parsed frontmatter `name`.

Add assertions inside existing `any(...)` checks:

```python
assert any(
    item.slug == "skill_manager"
    and item.name == "skill_manager"
    and item.registered_name == "skill__skill_manager"
    and item.source == "builtin"
    for item in installed
)
assert any(
    item.slug == "flight"
    and item.name == "flight"
    and item.registered_name == "skill__flight"
    and item.version == "1.2.3"
    and item.registry == "https://clawhub.ai"
    and item.managed is True
    and item.source == "managed"
    and item.path == managed
    for item in installed
)
assert any(
    item.slug == "manual"
    and item.name == "manual"
    and item.registered_name == "skill__manual"
    and item.version is None
    and item.registry is None
    and item.managed is False
    and item.source == "unmanaged"
    and item.path == unmanaged
    for item in installed
)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/unit/skills_registry/test_installer.py::test_list_installed_merges_managed_and_unmanaged_skills -q
```

Expected: FAIL with an `AttributeError` or failed assertion because `InstalledSkill` has no populated `name`.

- [ ] **Step 3: Add `name` to `InstalledSkill`**

In `sebastian/skills_registry/models.py`, add a defaulted field after `description` to avoid breaking existing positional construction:

```python
@dataclass(frozen=True)
class InstalledSkill:
    slug: str
    registered_name: str
    version: str | None
    registry: str | None
    managed: bool
    path: Path
    source: str = "managed"
    description: str = ""
    name: str = ""
```

- [ ] **Step 4: Populate `name` in `list_installed()`**

In `sebastian/skills_registry/installer.py`, update all `InstalledSkill(...)` construction sites in `list_installed()`:

```python
InstalledSkill(
    slug=path.name,
    registered_name=registered_name,
    version=None,
    registry=None,
    managed=False,
    path=path,
    source="builtin",
    description=metadata.description,
    name=metadata.name,
)
```

For managed Skills, use the metadata already read from disk:

```python
description=metadata.description if metadata is not None else "",
name=metadata.name if metadata is not None else "",
```

For unmanaged Skills, use `metadata.name`.

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
pytest tests/unit/skills_registry/test_installer.py::test_list_installed_merges_managed_and_unmanaged_skills -q
```

Expected: PASS.

- [ ] **Step 6: Run installer regression slice**

Run:

```bash
pytest tests/unit/skills_registry/test_installer.py -q
```

Expected: PASS.

## Task 2: Implement Multi-Token Local Search Scoring

**Files:**
- Modify: `sebastian/cli/skills.py`
- Test: `tests/unit/runtime/test_skills_cli.py`

- [ ] **Step 1: Write failing tests for OR matching and frontmatter name**

Add tests near existing `test_search_local_matches_description()`:

```python
def test_search_local_multi_token_query_matches_any_token(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        skills,
        "list_installed",
        lambda: [
            InstalledSkill(
                slug="flight_search",
                registered_name="skill__flight_search",
                version=None,
                registry=None,
                managed=False,
                path=tmp_path / "flight_search",
                source="unmanaged",
                description="Find flight and airfare options",
                name="flight_search",
            )
        ],
    )

    result = runner.invoke(app, ["skills", "search", "机票 航班 flight airfare"])

    assert result.exit_code == 0
    assert (
        "flight_search\tunmanaged\tskill__flight_search\t"
        "Find flight and airfare options"
    ) in result.output


def test_search_local_matches_frontmatter_name(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        skills,
        "list_installed",
        lambda: [
            InstalledSkill(
                slug="travel-pack",
                registered_name="skill__travel_pack",
                version=None,
                registry=None,
                managed=False,
                path=tmp_path / "travel-pack",
                source="unmanaged",
                description="Travel helper",
                name="airfare",
            )
        ],
    )

    result = runner.invoke(app, ["skills", "search", "airfare"])

    assert result.exit_code == 0
    assert "travel-pack\tunmanaged\tskill__travel_pack\tTravel helper" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/unit/runtime/test_skills_cli.py::test_search_local_multi_token_query_matches_any_token tests/unit/runtime/test_skills_cli.py::test_search_local_matches_frontmatter_name -q
```

Expected: FAIL because current search treats the whole query as one substring and does not inspect `skill.name`.

- [ ] **Step 3: Add tokenization and scoring helpers**

In `sebastian/cli/skills.py`, replace `_matches_local_skill()` and `_search_local()` with small helpers:

```python
def _search_tokens(query: str) -> tuple[str, ...]:
    seen: set[str] = set()
    tokens: list[str] = []
    for raw in query.split():
        token = raw.strip().casefold()
        if not token or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tuple(tokens)


def _contains(field: str, token: str) -> bool:
    return token in field.casefold()


def _score_local_skill(skill: InstalledSkill, tokens: tuple[str, ...]) -> int:
    score = 0
    slug = skill.slug.casefold()
    name = skill.name.casefold()
    registered_name = skill.registered_name.casefold()
    description = skill.description.casefold()
    for token in tokens:
        if token == slug or (name and token == name):
            score += 100
        elif token in slug or (name and token in name):
            score += 60
        if token in description:
            score += 30
        if token in registered_name:
            score += 15
    return score


def _source_sort_rank(source: str) -> int:
    return {"builtin": 0, "managed": 1, "unmanaged": 2}.get(source, 3)


def _search_local(query: str) -> list[InstalledSkill]:
    tokens = _search_tokens(query)
    if not tokens:
        return []
    scored = [
        (_score_local_skill(skill, tokens), skill)
        for skill in list_installed()
    ]
    matches = [(score, skill) for score, skill in scored if score > 0]
    matches.sort(
        key=lambda item: (
            -item[0],
            _source_sort_rank(item[1].source),
            item[1].slug,
        )
    )
    return [skill for _score, skill in matches]
```

Keep `_print_local_search_rows()` unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/unit/runtime/test_skills_cli.py::test_search_local_multi_token_query_matches_any_token tests/unit/runtime/test_skills_cli.py::test_search_local_matches_frontmatter_name -q
```

Expected: PASS.

- [ ] **Step 5: Add failing test for deterministic ranking**

Add:

```python
def test_search_local_sorts_stronger_name_match_before_description_match(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        skills,
        "list_installed",
        lambda: [
            InstalledSkill(
                slug="generic_travel",
                registered_name="skill__generic_travel",
                version=None,
                registry=None,
                managed=False,
                path=tmp_path / "generic_travel",
                source="unmanaged",
                description="airfare comparison helper",
                name="generic_travel",
            ),
            InstalledSkill(
                slug="flight_search",
                registered_name="skill__flight_search",
                version=None,
                registry=None,
                managed=False,
                path=tmp_path / "flight_search",
                source="unmanaged",
                description="travel helper",
                name="airfare",
            ),
        ],
    )

    result = runner.invoke(app, ["skills", "search", "airfare"])

    assert result.exit_code == 0
    assert result.output.index("flight_search") < result.output.index("generic_travel")
```

- [ ] **Step 6: Run ranking test**

Run:

```bash
pytest tests/unit/runtime/test_skills_cli.py::test_search_local_sorts_stronger_name_match_before_description_match -q
```

Expected: PASS after scoring implementation.

- [ ] **Step 7: Add and run whitespace query test**

Add:

```python
def test_search_local_whitespace_query_prints_empty_local_section(
    monkeypatch,
) -> None:
    calls = 0

    def fake_list_installed() -> list[InstalledSkill]:
        nonlocal calls
        calls += 1
        return []

    monkeypatch.setattr(skills, "list_installed", fake_list_installed)

    result = runner.invoke(app, ["skills", "search", "   "])

    assert result.exit_code == 0
    assert result.output == "LOCAL\n"
    assert calls == 0
```

Run:

```bash
pytest tests/unit/runtime/test_skills_cli.py::test_search_local_whitespace_query_prints_empty_local_section -q
```

Expected: PASS. If Typer rejects a whitespace argument in this exact form, adapt the test to call `skills._search_local("   ")` and `_print_local_search_rows(...)` directly.

- [ ] **Step 8: Run CLI search regression slice**

Run:

```bash
pytest tests/unit/runtime/test_skills_cli.py -q
```

Expected: PASS.

## Task 3: Strengthen Skill Discovery Prompt

**Files:**
- Modify: `sebastian/core/base_agent.py`
- Test: `tests/unit/core/test_prompt_builder.py`

- [ ] **Step 1: Write failing prompt assertions**

Update `test_system_prompt_includes_skill_management_bootstrap()`:

```python
assert "search local Skills before using generic tools" in agent.system_prompt
assert "机票 航班 飞机票 flight airfare airline ticket travel booking" in agent.system_prompt
assert "sebastian skills show <name-or-slug> --body" in agent.system_prompt
assert "Registry" in agent.system_prompt
assert "only when the user wants to find new Skills to install" in agent.system_prompt
```

Keep existing assertions that the prompt says not to use generic `Read` for Skill directories.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/unit/core/test_prompt_builder.py::test_system_prompt_includes_skill_management_bootstrap -q
```

Expected: FAIL because current prompt does not include domain-first discovery guidance or multilingual examples.

- [ ] **Step 3: Update `_skill_management_section()`**

In `sebastian/core/base_agent.py`, extend the returned lines after the CLI command list and before mutation command guidance:

```python
"For reusable domain tasks, search local Skills before using generic tools. "
"This includes travel, flights, hotels, calendar, meetings, email, documents, "
"spreadsheets, code, repositories, browser automation, and other repeatable workflows.",
"If the user uses Chinese or other non-English terms, include the user's "
"keywords plus likely English synonyms in the search query, separated by spaces.",
"Examples:",
'- `sebastian skills search "机票 航班 飞机票 flight airfare airline ticket travel booking"`',
'- `sebastian skills search "酒店 住宿 hotel lodging accommodation travel"`',
'- `sebastian skills search "日程 会议 calendar schedule meeting"`',
"If local search returns plausible candidates, read the chosen Skill body with "
"`sebastian skills show <name-or-slug> --body` before acting.",
"If no plausible Skill is found, continue with normal tools.",
```

Keep the existing lines:

- local search default is local
- registry search only for new install discovery
- install/update/remove are explicit user management operations
- Skill management uses CLI instead of generic Read

- [ ] **Step 4: Run prompt tests**

Run:

```bash
pytest tests/unit/core/test_prompt_builder.py -q
```

Expected: PASS.

## Task 4: Documentation Updates

**Files:**
- Modify: `docs/superpowers/specs/2026-05-08-skill-progressive-disclosure-design.md`
- Modify: `docs/architecture/spec/core/system-prompt.md`
- Modify: `docs/architecture/spec/capabilities/skill-package-manager.md`
- Modify: `sebastian/capabilities/skills/README.md`
- Modify: `sebastian/cli/README.md`

- [ ] **Step 1: Update progressive disclosure spec prompt section**

In `docs/superpowers/specs/2026-05-08-skill-progressive-disclosure-design.md`, update section `## 7. Prompt Bootstrap` to include the new discovery policy and multilingual examples. Keep the core progressive disclosure rule: no installed Skill listing and no body injection.

- [ ] **Step 2: Update architecture spec docs**

In `docs/architecture/spec/core/system-prompt.md`, add that `BASE` prompt includes a fixed Skill Management bootstrap telling agents to search local Skills before generic tools for reusable domain tasks, and to include English synonyms for non-English user requests.

In `docs/architecture/spec/capabilities/skill-package-manager.md`, update CLI search semantics:

- default local
- multi-token OR matching
- fields: slug, frontmatter name, registered_name, description
- deterministic score sort
- no keywords/aliases/package mutation

- [ ] **Step 3: Update module READMEs**

In `sebastian/capabilities/skills/README.md`, update Package Manager lifecycle or CLI behavior with:

```markdown
`search <query>` tokenizes local queries on whitespace and OR-matches slug,
frontmatter name, registered name, and description. Agents should include
likely English synonyms when the user asks in Chinese or another language.
```

In `sebastian/cli/README.md`, update the `skills.py` section with the same local search behavior.

- [ ] **Step 4: Search for stale wording**

Use PyCharm MCP search first, or fallback to:

```bash
python3 - <<'PY'
from pathlib import Path
for path in Path('.').rglob('*.md'):
    if '.git' in path.parts or 'graphify-out' in path.parts:
        continue
    text = path.read_text(encoding='utf-8', errors='ignore')
    if 'keywords' in text and 'Skill' in text:
        print(path)
PY
```

Expected: No new docs imply `keywords` or aliases are part of this phase.

## Task 5: Final Verification

**Files:**
- Verify all touched files.

- [ ] **Step 1: Run focused unit tests**

Run:

```bash
pytest tests/unit/runtime/test_skills_cli.py tests/unit/skills_registry/test_installer.py tests/unit/core/test_prompt_builder.py -q
```

Expected: PASS.

- [ ] **Step 2: Run broader relevant regression slice**

Run:

```bash
pytest tests/unit/runtime/test_skills_cli.py tests/unit/skills_registry/test_installer.py tests/unit/capabilities/test_skills_loader.py tests/unit/capabilities/test_registry_filtering.py tests/unit/identity/test_policy_gate.py tests/unit/core/test_base_agent.py tests/unit/core/test_agent_loop.py tests/unit/core/test_stream_helpers.py -q
```

Expected: PASS.

- [ ] **Step 3: Run graphify rebuild after code changes**

Run:

```bash
python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```

Expected: command exits 0. It may skip HTML generation if the graph is too large.

- [ ] **Step 4: Review git diff**

Run:

```bash
git status --short
git diff -- sebastian/cli/skills.py sebastian/skills_registry/models.py sebastian/skills_registry/installer.py sebastian/core/base_agent.py tests/unit/runtime/test_skills_cli.py tests/unit/skills_registry/test_installer.py tests/unit/core/test_prompt_builder.py
```

Expected:

- No Skill-as-provider-tool reintroduction.
- No `keywords`, aliases, or install-time mutation.
- Existing immediate-availability wording changes are preserved.
- Search still defaults to local and does not call registry unless requested.

## Task 6: Atomic Commit

**Files:**
- Stage only files touched for this feature plus required docs.

- [ ] **Step 1: Stage specific files**

Run:

```bash
git add sebastian/skills_registry/models.py \
  sebastian/skills_registry/installer.py \
  sebastian/cli/skills.py \
  sebastian/core/base_agent.py \
  tests/unit/runtime/test_skills_cli.py \
  tests/unit/skills_registry/test_installer.py \
  tests/unit/core/test_prompt_builder.py \
  docs/superpowers/specs/2026-05-08-skill-progressive-disclosure-design.md \
  docs/architecture/spec/core/system-prompt.md \
  docs/architecture/spec/capabilities/skill-package-manager.md \
  sebastian/capabilities/skills/README.md \
  sebastian/cli/README.md
```

If the earlier immediate-availability wording changes are still uncommitted in the same files, include them only if they are intentionally part of the current branch cleanup. Do not stage unrelated files accidentally.

- [ ] **Step 2: Inspect staged diff**

Run:

```bash
git diff --cached --name-status
git diff --cached
```

Expected: staged changes match this plan and do not include unrelated work.

- [ ] **Step 3: Commit**

Run:

```bash
git commit -m "feat(skills): 增强本地 Skill 多语言发现" -m "Co-Authored-By: gpt 5.5 <noreply@openai.com>"
```

Expected: commit succeeds.
