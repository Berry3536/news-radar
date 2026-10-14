# Implementation conventions (stark-kit)

Shared conventions for every repository that uses stark-kit. These are rules for how cross-cutting
code is written; package layout and layering are declared per repository and checked by
`kit.py doctor` (`layout`) and import-linter (`[tool.importlinter]` in `pyproject.toml`).

## Repository layout

| `kit.json` `layout` | Required | Notes |
|---|---|---|
| `package` | `pyproject.toml`, `.python-version`, `uv.lock`, `src/<pkg>/__init__.py`, `tests/` | No `*.py` at the top level except `run.py` (frozen-app entry point). Maintainer scripts go in `tools/`. |
| `script` | `pyproject.toml`, `.python-version`, `uv.lock` | Flat layout for single-module tools; `tests/` optional. |

Both: `.editorconfig`, `.github/dependabot.yml` (written by `kit.py sync` if absent), dev tooling in
`[dependency-groups] dev`, runtime optional features as extras.

## Layering

Declare the allowed import directions in `pyproject.toml` and run `uv run lint-imports`
(enable with `lint-imports: true` in the CI caller). Example for a ui → application → core/infrastructure → domain app:

```toml
[tool.importlinter]
root_package = "swap_candb"

[[tool.importlinter.contracts]]
name = "ui depends only on application"
type = "forbidden"
source_modules = ["swap_candb.ui"]
forbidden_modules = ["swap_candb.infrastructure", "swap_candb.domain", "swap_candb.core"]
```

A lower layer never imports a higher one; `app`/`ui`/`main` is the only place that wires everything.
Lazy imports to break a cycle are a smell — move the shared piece down instead.

## Logging

- One named root logger per application (`"alfred"`, `"swap_candb"`), configured once at startup
  by a `setup_logging()`/`setup_logger()` in the app layer; libraries never configure handlers.
- Module loggers are children of that root: `logging.getLogger(f"{APP_LOGGER}.{__name__}")` or a
  package `__name__` that already lives under the root package name. Never a logger outside the tree.
- Never log secrets; redact at the boundary (see alfred `security/redaction.py` for the pattern).

## Configuration

- **strict** repos: unknown keys, wrong types, relative paths where absolute ones are required,
  unreadable files → reject with a typed error (fail closed). No silent defaults for anything that
  changes external behavior.
- **standard** repos: missing optional settings fall back to documented defaults; corrupt state
  files are logged and replaced, not propagated.
- One parser per config section, pure (dict in → frozen dataclass out), tested with golden inputs.

## Files and state

- Small JSON/YAML state: write atomically (temp file in the same directory, `fsync`, `os.replace`).
  alfred `core/durable.py` is the reference implementation; copy it, do not import across repos.
- Append-only journals: one line per record (JSONL), `fsync` per append, sidecar lock when more than
  one process may write.
- App data lives under one per-app directory (`~/.<app>/`), defined in exactly one module.

## Time

- Timestamps are timezone-aware UTC (`datetime.now(UTC)`); naive datetimes are rejected at the
  boundary (`_require_utc_datetime`-style check in one place, imported everywhere).
- Day-based limits key on the UTC date; render local time only in UI/output.

## Money and precision

- `Decimal` for money, quantities, fees; never `float`. Parse from strings, not floats.

## Errors

- One base exception per package (`AlfredError`, `CANdbConvertError`) with typed subclasses and
  stable codes where users see them. Catch at boundaries, not in helpers.
- External effects (orders, payments, file publishing): anything ambiguous is recorded as unknown
  and surfaced for manual follow-up, never retried blindly.
