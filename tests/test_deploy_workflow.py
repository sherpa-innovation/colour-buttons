from __future__ import annotations

import re
from pathlib import Path

WORKFLOW_PATH = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "deploy.yml"

# The file's content before this requirement's fix, one entry per line, in order.
ORIGINAL_LINES = [
    '# Made by SHERPA: deploys each release to Azure. A change to it is a reviewed change like any other.',
    'name: deploy',
    'on:',
    '  push:',
    '    tags: ["v*"]',
    'permissions:',
    '  id-token: write',
    '  contents: read',
    'concurrency:',
    '  group: production',
    '  cancel-in-progress: false',
    'jobs:',
    '  deploy:',
    '    runs-on: ubuntu-latest',
    '    environment:',
    '      name: production',
    '      url: ${{ steps.deploy.outputs.webapp-url }}',
    '    steps:',
    '      - uses: actions/checkout@v4',
    '      - name: Sign in to Azure (no password: Azure trusts this environment)',
    '        uses: azure/login@v2',
    '        with:',
    '          client-id: ${{ vars.AZURE_CLIENT_ID }}',
    '          tenant-id: ${{ vars.AZURE_TENANT_ID }}',
    '          subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}',
    '      - name: Make the web app the first time',
    '        env:',
    '          GROUP: ${{ vars.AZURE_RESOURCE_GROUP }}',
    '          PLAN: ${{ vars.AZURE_APP_SERVICE_PLAN }}',
    '          APP: ${{ vars.AZURE_WEBAPP_NAME }}',
    '        run: |',
    '          if ! az webapp show -g "$GROUP" -n "$APP" >/dev/null 2>&1; then',
    '            az webapp create -g "$GROUP" -p "$PLAN" -n "$APP" --runtime "PYTHON:3.13" --output none',
    '          fi',
    '          az webapp config set -g "$GROUP" -n "$APP" --output none \\',
    '            --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 --chdir src app:app"',
    '          az webapp config appsettings set -g "$GROUP" -n "$APP" --output none \\',
    '            --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true DATA_DIR=/home/data',
    '      - name: Deploy this release',
    '        id: deploy',
    '        uses: azure/webapps-deploy@v3',
    '        with:',
    '          app-name: ${{ vars.AZURE_WEBAPP_NAME }}',
    '          package: .',
]

SIGN_IN_LINE_INDEX = 19
OLD_SIGN_IN_LINE = ORIGINAL_LINES[SIGN_IN_LINE_INDEX]
NEW_SIGN_IN_LINE = "      - name: Sign in to Azure with no password (Azure trusts this environment)"


def read_workflow() -> str:
    """The raw text of the deploy workflow file."""
    return WORKFLOW_PATH.read_text()


def ambiguous_plain_scalar_lines(text: str) -> list[str]:
    """Lines whose unquoted value has a bare ': ', which YAML reads as an accidental nested key."""
    bad: list[str] = []
    skip_below_indent: int | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if skip_below_indent is not None:
            if indent > skip_below_indent:
                continue
            skip_below_indent = None
        match = re.match(r"^\s*(?:-\s+)?[A-Za-z][\w-]*:\s*(.*)$", line)
        if not match:
            continue
        value = match.group(1).strip()
        if not value:
            continue
        if value[0] in "|>'\"[{&*!#":
            if value in ("|", ">"):
                skip_below_indent = indent
            continue
        without_templates = re.sub(r"\$\{\{.*?\}\}", "", value)
        if ": " in without_templates:
            bad.append(line)
    return bad


def test_deploy_workflow_parses_as_yaml_ac1() -> None:
    """AC-1: no line has a value YAML reads as an accidental nested key; the job is named deploy."""
    text = read_workflow()
    assert ambiguous_plain_scalar_lines(text) == []
    assert text.splitlines()[1] == "name: deploy"


def test_deploy_workflow_triggers_on_v_tags_only_ac1() -> None:
    """AC-1: the workflow still runs on push of v* tags only, no other trigger."""
    text = read_workflow()
    on_section = text.split("on:\n", 1)[1].split("permissions:", 1)[0]
    assert on_section.strip("\n") == '  push:\n    tags: ["v*"]'


def test_deploy_workflow_actions_and_order_ac2() -> None:
    """AC-2: the deploy job still uses checkout@v4, azure/login@v2 and webapps-deploy@v3, in that order."""
    text = read_workflow()
    assert "      - uses: actions/checkout@v4" in text
    checkout_at = text.index("actions/checkout@v4")
    login_at = text.index("azure/login@v2")
    deploy_action_at = text.index("azure/webapps-deploy@v3")
    assert checkout_at < login_at < deploy_action_at


def test_deploy_workflow_login_settings_unchanged_ac2() -> None:
    """AC-2: the Azure login step keeps its settings (client-id, tenant-id, subscription-id)."""
    text = read_workflow()
    expected = (
        "        uses: azure/login@v2\n"
        "        with:\n"
        "          client-id: ${{ vars.AZURE_CLIENT_ID }}\n"
        "          tenant-id: ${{ vars.AZURE_TENANT_ID }}\n"
        "          subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}"
    )
    assert expected in text


def test_deploy_workflow_webapps_deploy_settings_unchanged_ac2() -> None:
    """AC-2: the webapps-deploy step keeps its id, app-name and package settings."""
    text = read_workflow()
    expected = (
        "      - name: Deploy this release\n"
        "        id: deploy\n"
        "        uses: azure/webapps-deploy@v3\n"
        "        with:\n"
        "          app-name: ${{ vars.AZURE_WEBAPP_NAME }}\n"
        "          package: ."
    )
    assert expected in text


def test_deploy_workflow_sign_in_step_renamed_ac3() -> None:
    """AC-3: the sign-in step is renamed to drop the stray colon-space, with the exact new wording."""
    text = read_workflow()
    assert NEW_SIGN_IN_LINE in text.splitlines()
    assert OLD_SIGN_IN_LINE not in text


def test_deploy_workflow_only_sign_in_line_changes_ac3() -> None:
    """AC-3: every other line of the workflow file is byte-for-byte unchanged by the fix."""
    actual_lines = read_workflow().splitlines()
    assert len(actual_lines) == len(ORIGINAL_LINES)
    for index, (actual, original) in enumerate(zip(actual_lines, ORIGINAL_LINES)):
        if index == SIGN_IN_LINE_INDEX:
            assert actual == NEW_SIGN_IN_LINE
        else:
            assert actual == original, f"line {index + 1} changed unexpectedly"
