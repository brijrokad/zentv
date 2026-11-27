"""Ground rule 5, checked on the final shell string of every command (the second net).

`commands.py` has no constructor for any of these, so a hit here means a bug. The check runs
anyway, on every command, read-only ones included.
"""

from __future__ import annotations

import re

from .errors import Refused

# Characters a token may contain once validated. Anything else (; & | ` $ < > newline, quotes,
# spaces inside a token...) could chain or redirect on the TV's shell.
SAFE_TOKEN = re.compile(r"^[A-Za-z0-9._:/=@,+\-]+$")

RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("pm uninstall (any form)", re.compile(r"(^|\s)(pm|cmd\s+package)\s+uninstall\b|(^|\s)uninstall(\s|$)")),
    ("pm clear", re.compile(r"\b(pm|cmd\s+package)\s+clear\b")),
    ("pm hide", re.compile(r"\b(pm|cmd\s+package)\s+hide\b")),  # unhide only via commands.unhide()
    ("pm suspend", re.compile(r"\b(pm|cmd\s+package)\s+suspend\b")),
    ("dpm", re.compile(r"(^|\s)dpm(\s|$)|\bcmd\s+device_policy\b")),
    ("setprop persist.*", re.compile(r"\bsetprop\s+persist\.")),
    (
        "package verifier settings",
        re.compile(
            r"verifier_verify_adb_installs|package_verifier_enable|"
            r"verifier_|upload_apk_enable"
        ),
    ),
    ("ADB switched on", re.compile(r"\bsettings\s+put\s+global\s+adb(_wifi)?_enabled\s+(?!0$)\S+")),
    ("WRITE_SECURE_SETTINGS grant", re.compile(r"WRITE_SECURE_SETTINGS")),
    ("permission grant", re.compile(r"\b(pm|cmd\s+package)\s+grant\b")),
    (
        "install confirmation bypass",
        re.compile(
            r"\binstall\b.*(\s-g\b|\s-t\b|--bypass|--force-queryable|"
            r"--skip-verification|--disable-verification)"
        ),
    ),
    ("background loop", re.compile(r"^(while|until|nohup|setsid|crontab|watch|sh|su)(\s|$)")),
    (
        "start a factory menu",
        re.compile(r"^(am|monkey|cmd\s+activity)\s.*(factorymenu|com\.tcl\.factory\.view)"),
    ),
)


def check_tokens(argv: tuple[str, ...]) -> None:
    for tok in argv:
        if not SAFE_TOKEN.fullmatch(tok):
            raise Refused(f"refused: unsafe characters in {tok!r} (shell metacharacters are never sent)")


def check(shell_string: str, argv: tuple[str, ...] | None = None) -> None:
    """Raise Refused if the command matches any ground-rule-5 pattern."""
    if argv is not None:
        check_tokens(argv)
    for name, pattern in RULES:
        if pattern.search(shell_string):
            raise Refused(f"refused by ground rule 5 ({name}): {shell_string}")
