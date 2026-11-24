# Project conventions (Python web starter)

Read this before changing anything. Rules marked *enforced* are checked by the platform and fail the step if broken;
the rest are checked by the reviewers.

## Project overview
- A small web application: `src/app.py` is a WSGI application (`app`) serving HTML pages and a JSON API.
- What it does, and why, is in the approved requirement and the approved architecture (HLD.md); this file says how it is built.

## Stack and dependencies
- Python 3.13, standard library only in `src/` (`wsgiref`, `json`, `html`, `pathlib`).
- In production gunicorn serves `app:app` (requirements.txt); nothing in `src/` imports it.
- Add no dependency unless the approved architecture names it.

## Layout
- Code lives in `src/` as plain modules; `src/app.py` holds the WSGI entry point `app`.
- Tests live in `tests/test_<module>.py`, one file per module; once a module's test file holds approved,
  protected tests, add further coverage for it in another `tests/test_<module>_<topic>.py` file rather than
  editing the protected one [cite: tests/test_app_error_handling.py].
- Data the app keeps goes under the folder named by the `DATA_DIR` environment variable (default `./data`); never
  next to the code.

## Build and test
- `python -m ruff check .` and `python -m pytest -q` (*enforced*: the gate runs both).
- Run it locally: `python src/app.py` serves it on port 8000.

## Conventions
- Type-annotate every public function and give it a one-line docstring.
- Escape everything put into HTML (`html.escape`); build no HTML from unescaped input.
- Validate input where it enters and answer a bad request with 400 and a message; never a stack trace.
- Lint-clean at line length 110 (*enforced*).

## Coding conventions
- Small functions; no mutable global state except the data folder's files; no bare `except`.

## Testing
- Test the app by calling it as a WSGI application (see `tests/test_app.py`): status, headers and body.
- Tests are deterministic: a temporary `DATA_DIR` per test, no network, no sleeps.
- Never delete, skip or weaken an existing test to make the checks pass (*enforced*: protect_tests).

## Boundaries
- Change only the files your requirement needs.
- Don't edit CLAUDE.md, `pyproject.toml`, requirements.txt or CI and deployment config unless the requirement is
  about them.
- Don't commit or merge; the platform commits your changes and merges approved work.

## Security
- No secrets, tokens or credentials in code, tests or logs.
- No `eval`/`exec`, no `shell=True`, no unpickling.
