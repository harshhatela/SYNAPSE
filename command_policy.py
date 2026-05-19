import re


CONFIRMATION_PREFIX_RE = re.compile(
    r"^\s*(?:CONFIRMED|CONFIRMED_DESTRUCTIVE|SYNAPSE_CONFIRM_DESTRUCTIVE)\s*:\s*",
    re.IGNORECASE,
)


_COMMON_DESTRUCTIVE_PATTERNS = [
    r"\brm\s+.*(?:-[^\s]*[rf]|--recursive|--force)\b",
    r"\bremove-item\b.*(?:-recurse|-force)\b",
    r"\bformat(?:-volume)?\b",
    r"\bmkfs(?:\.[a-z0-9]+)?\b",
    r"\bdd\s+.*\bof=",
    r"\bdrop\s+(?:database|schema|table)\b",
    r"\btruncate\s+table\b",
]

_TOOL_DESTRUCTIVE_PATTERNS = {
    "docker": [
        r"^(?:container\s+)?rm\b",
        r"^(?:image\s+)?rmi\b",
        r"^(?:system|container|image|volume|network)\s+prune\b",
        r"^(?:volume|network)\s+rm\b",
    ],
    "kubectl": [
        r"^delete\b",
        r"^replace\b.*--force\b",
        r"^scale\b.*--replicas\s*=\s*0\b",
    ],
    "aws": [
        r"\bterminate-instances\b",
        r"\bdelete-[a-z0-9-]+\b",
        r"\bremove-[a-z0-9-]+\b",
        r"\bderegister-[a-z0-9-]+\b",
    ],
}


def strip_confirmation_prefix(command: str) -> tuple[str, bool]:
    """Remove the explicit destructive-action confirmation marker if present."""
    match = CONFIRMATION_PREFIX_RE.match(command or "")
    if not match:
        return command, False
    return command[match.end():].lstrip(), True


def is_destructive_command(command: str, tool_name: str) -> bool:
    """Best-effort guardrail for obviously destructive infrastructure commands."""
    normalized = " ".join((command or "").strip().lower().split())
    if not normalized:
        return False

    for pattern in _COMMON_DESTRUCTIVE_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            return True

    for pattern in _TOOL_DESTRUCTIVE_PATTERNS.get(tool_name.lower(), []):
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            return True
    return False


def enforce_command_policy(command: str, tool_name: str) -> tuple[str, str | None]:
    """Return (clean_command, error).

    Destructive commands must be prefixed with `CONFIRMED:` by the agent. The
    prompt tells the agent to add this prefix only when the user explicitly
    confirmed the destructive action; the tool strips it before execution.
    """
    clean_command, confirmed = strip_confirmation_prefix(command)
    if is_destructive_command(clean_command, tool_name) and not confirmed:
        return clean_command, (
            "Potentially destructive command blocked. Ask the user for explicit "
            "confirmation, then retry with the tool command prefixed by "
            "`CONFIRMED:`."
        )
    return clean_command, None
