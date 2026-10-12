#!/usr/bin/env python3
"""Load the machine-local list of private terms this public repo must not hold.

The list names the employer, holdings and nicknames that must never be
published, plus the vendor names the site masks. Writing them in the repo
would publish them, so they live in a JSON file on each machine that runs the
pipeline:

    $SKILLS_RADAR_PRIVATE_TERMS, or ~/.config/skills-radar/private_terms.json

    {"banned": ["<regex>", ...], "redact": [["<regex>", "<replacement>"], ...]}

bin/check_privacy.py matches "banned" case-sensitively; bin/build_site.py
masks "redact" case-insensitively. A missing or malformed file raises
PrivateTermsError, so both stop instead of running with an empty list.
Error messages name the file and the problem, never a term.
"""

import json
import os
import re
from pathlib import Path


ENV_VAR = "SKILLS_RADAR_PRIVATE_TERMS"
DEFAULT_PATH = Path.home() / ".config" / "skills-radar" / "private_terms.json"


class PrivateTermsError(RuntimeError):
    """The private term list is missing or unusable; the caller must stop."""


def terms_path():
    value = os.environ.get(ENV_VAR)
    return Path(value) if value else DEFAULT_PATH


def _compile(pattern, flags, where):
    if not isinstance(pattern, str) or not pattern:
        raise PrivateTermsError(f"{where} must be a non-empty string")
    try:
        return re.compile(pattern, flags)
    except re.error:
        raise PrivateTermsError(f"{where} is not a valid regex") from None


def load_private_terms(path=None):
    """Return (banned patterns, [(redact pattern, replacement), ...])."""
    path = Path(path) if path else terms_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise PrivateTermsError(
            f"private term list not found: {path} (create it or set {ENV_VAR})"
        ) from None
    except (OSError, ValueError) as exc:
        raise PrivateTermsError(
            f"private term list unreadable: {path} ({type(exc).__name__})"
        ) from None
    if not isinstance(data, dict):
        raise PrivateTermsError(f"private term list is not a JSON object: {path}")
    banned, redact = data.get("banned"), data.get("redact")
    if not isinstance(banned, list) or not banned:
        raise PrivateTermsError(f"'banned' must be a non-empty list: {path}")
    if not isinstance(redact, list) or not redact:
        raise PrivateTermsError(f"'redact' must be a non-empty list: {path}")
    banned_patterns = [_compile(item, 0, f"banned[{i}]") for i, item in enumerate(banned)]
    redact_pairs = []
    for i, pair in enumerate(redact):
        if not (isinstance(pair, list) and len(pair) == 2
                and isinstance(pair[1], str) and pair[1]):
            raise PrivateTermsError(f"redact[{i}] must be [regex, non-empty replacement]")
        redact_pairs.append((_compile(pair[0], re.I, f"redact[{i}]"), pair[1]))
    return banned_patterns, redact_pairs
