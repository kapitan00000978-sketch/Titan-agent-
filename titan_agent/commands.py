"""Slash commands for TITAN AGENT (Hermes-class command layer).

Commands turn a short user input like `/review tools.py` into a specialized
prompt + mode + effort, so the agent frames the task correctly without the
user having to write a long instruction. Used by the CLI and the Web UI.

Pure functions, zero dependencies: the Web UI mirrors these expansions in
JS (web_ui/app.js) so the browser (Puter.js) path behaves identically.
"""

# name -> definition. "arg" is appended after the template.
COMMANDS = {
    "plan": {
        "description": "Create a detailed, step-by-step implementation plan for a task.",
        "mode": "deep",
        "effort": "high",
        "template": (
            "Create a detailed, step-by-step implementation plan for the following "
            "task. Break it into phases/milestones with clear done-criteria, list the "
            "files/tools you would touch, the risks, and end with the single next "
            "action to take now.\n\nTASK: {arg}"
        ),
    },
    "review": {
        "description": "Perform a rigorous code review of a file, diff, or piece of code.",
        "mode": "deep",
        "effort": "high",
        "template": (
            "Perform a rigorous code review of the following target. Use the coding-rules "
            "and github-ops skills. Check for bugs, edge cases, error handling, naming, "
            "security issues and test coverage. Report findings by severity "
            "(Critical / Important / Minor / Nit) with concrete fixes.\n\nREVIEW TARGET: {arg}"
        ),
    },
    "security-scan": {
        "description": "Run a security audit of a file, folder, or dependency list.",
        "mode": "deep",
        "effort": "ultra",
        "template": (
            "Run a security audit on the following target using the security-ops skill. "
            "Threat-model first: check for injection, secrets, path traversal, SSRF, unsafe "
            "deserialization, and dependency vulnerabilities. Report by severity with fixes.\n\nSCAN TARGET: {arg}"
        ),
    },
    "research": {
        "description": "Deep multi-source research on a topic (uses web search).",
        "mode": "deep_search",
        "effort": "high",
        "template": (
            "Research the following topic thoroughly using the research-ops skill. Find "
            "multiple sources, cross-check claims, prefer recently updated primary sources, "
            "and cite everything you actually retrieved.\n\nTOPIC: {arg}"
        ),
    },
    "explain": {
        "description": "Explain a file or concept in depth.",
        "mode": "deep",
        "effort": "medium",
        "template": (
            "Explain the following in depth: what it is, how it works, why it matters, "
            "and any caveats. Use concrete examples.\n\nSUBJECT: {arg}"
        ),
    },
    "fix": {
        "description": "Diagnose and fix a bug or failing behavior.",
        "mode": "deep",
        "effort": "high",
        "template": (
            "Diagnose and fix the following issue. Use the coding-rules skill: reproduce "
            "or understand the cause, make the smallest correct change, then verify it "
            "actually works before reporting.\n\nISSUE: {arg}"
        ),
    },
    "test": {
        "description": "Write or run tests for a file or feature.",
        "mode": "deep",
        "effort": "medium",
        "template": (
            "Write and/or run tests for the following target using the coding-rules skill. "
            "Cover the happy path, edge cases, and error paths. Report test results.\n\nTEST TARGET: {arg}"
        ),
    },
    "remember": {
        "description": "Store a fact in long-term memory (Memory Vault, global scope).",
        "mode": "fast",
        "effort": "auto",
        "template": (
            "Save the following to memory using memory_save with a clear short key, then "
            "confirm it was saved.\n\nFACT: {arg}"
        ),
    },
    "handoff": {
        "description": "Leave a handoff note for the next agent/session.",
        "mode": "fast",
        "effort": "auto",
        "template": (
            "Leave a handoff note using handoff_create summarizing current state, "
            "decisions, and next steps. Keep it concise and actionable.\n\nNOTE: {arg}"
        ),
    },
    "blue-team": {
        "description": "Run continuous blue team defensive audit and policy verification.",
        "mode": "deep",
        "effort": "high",
        "template": (
            "Run a thorough BLUE TEAM defensive security audit on the following target. "
            "Inspect for prompt injection vulnerabilities, secret leaks, unauthorized access points, "
            "and security policy compliance. Produce a hardened defense plan.\n\nDEFENSE TARGET: {arg}"
        ),
    },
    "red-team": {
        "description": "Trigger emergency / manual red team adversarial penetration and counter-strike.",
        "mode": "deep",
        "effort": "ultra",
        "template": (
            "Conduct an EMERGENCY RED TEAM adversarial penetration test and exploit analysis on the following target. "
            "Deconstruct potential attack vectors, test boundary conditions, classify MITRE ATT&CK techniques, "
            "and generate immediate containment countermeasures.\n\nATTACK/AUDIT TARGET: {arg}"
        ),
    },
    "sast": {
        "description": "Run Static Application Security Testing & OWASP Top 10 code audit.",
        "mode": "deep",
        "effort": "high",
        "template": (
            "Perform a deep SAST & OWASP Top 10 static security audit on the following file or code. "
            "Use the sast_scan tool. Check for SQLi, command injection, path traversal, unsafe deserialization, "
            "and SSRF. Report each vulnerability with line numbers and remediations.\n\nSAST TARGET: {arg}"
        ),
    },
    "deps-audit": {
        "description": "Audit project dependencies and manifests for known CVEs.",
        "mode": "fast",
        "effort": "medium",
        "template": (
            "Audit project dependencies for known security vulnerabilities and CVEs using the dependency_audit tool. "
            "Report vulnerable packages and recommended upgrade versions.\n\nMANIFEST: {arg}"
        ),
    },
    "secret-scan": {
        "description": "Scan files or text for leaked API keys, tokens, and high-entropy credentials.",
        "mode": "fast",
        "effort": "medium",
        "template": (
            "Scan the following target for leaked credentials, API keys, tokens, and high-entropy secrets "
            "using the secret_scan tool. Provide a sanitized redaction report.\n\nTARGET: {arg}"
        ),
    },
}

# Commands handled locally (no LLM call needed).
LOCAL_COMMANDS = {
    "help": "List all slash commands and usage.",
    "dashboard": "Display interactive system and agent dashboard.",
    "security-status": "View real-time Dual-Shield security defense and sentinel status.",
    "banned-ips": "View and manage defensively banned IP addresses and Geo-logs. Usage: /banned-ips [unban <ip>]",
    "files": "Browse workspace files and project structure. Usage: /files [filter]",
    "status": "Show current provider, model, mode and effort.",
    "mode": "Switch mode: fast, deep, deep_search. Usage: /mode deep",
    "effort": "Switch effort: auto, low, medium, high, ultra. Usage: /effort high",
    "skills": "List available skill playbooks.",
    "memory": "Search long-term memory. Usage: /memory <query>",
    "handoffs": "List open handoff notes.",
    "queue": "Autonomous task queue: list/stats/enqueue/cancel. Usage: /queue list | /queue stats | /queue add <task> | /queue cancel <id>",
    "daemon": "Run the autonomous daemon once. Usage: /daemon [--poll <sec>] (runs until Ctrl+C)",
    "clear": "Clear the current session's conversation history.",
    "exit": "Exit the CLI (also: quit).",
}

ALL_COMMANDS = {**LOCAL_COMMANDS, **{k: v["description"] for k, v in COMMANDS.items()}}


def expand_slash(text: str) -> dict | None:
    """If `text` starts with a known slash command, return
    {"command", "arg", "mode", "effort", "prompt"} to send to the agent.
    Returns None when the input is not a slash command (send as-is)."""
    if not text or not text.startswith("/"):
        return None
    stripped = text[1:].strip()
    if not stripped:
        return None
    parts = stripped.split(None, 1)
    name = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    cmd = COMMANDS.get(name)
    if cmd is None:
        return None
    prompt = cmd["template"].format(arg=arg or "(no argument provided — ask about the general case)")
    return {
        "command": name,
        "arg": arg,
        "mode": cmd["mode"],
        "effort": cmd["effort"],
        "prompt": prompt,
    }


def parse_local(text: str) -> dict | None:
    """If `text` is a local (no-LLM) command like /help or /status, return a
    dict describing it; otherwise None. The caller renders the response."""
    if not text or not text.startswith("/"):
        return None
    stripped = text[1:].strip()
    if not stripped:
        return None
    parts = stripped.split(None, 1)
    name = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    if name not in LOCAL_COMMANDS:
        return None
    return {"name": name, "arg": arg}