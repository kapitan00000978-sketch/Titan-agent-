"""
Phase 11 — Intent Router: deterministic, LLM-free task -> specialist mapping.

Unlike the Phase 2 classifier (which picks a *task type* for code generation),
the Intent Router decides which STAFF role should carry out an incoming
request — the routing logic itself, as a first-class module usable by the
parent agent via the `subagent_route` tool and by the `router` specialist role.

Design goals
------------
- Pure + deterministic: no network, no model, no clock -> trivially testable.
- Rule-based keyword scoring across the whole Phase 9/11 roster (17 roles).
- Multi-role aware: the highest-scoring role is primary; other matched roles
  are returned as supporting roles so the parent can fan out a team.
- Never raises: empty/unknown input falls back to the generalist role.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntentRoute:
    """One routing decision: who does the work."""

    primary_role: str
    supporting_roles: tuple[str, ...] = ()
    reason: str = ""

    def plan_text(self) -> str:
        parts = [f"Primary: {self.primary_role}"]
        if self.supporting_roles:
            parts.append("Supporting: " + ", ".join(self.supporting_roles))
        if self.reason:
            parts.append(f"Reason: {self.reason}")
        return "\n".join(parts)


# (keywords, role) — ORDER MATTERS for tie-breaking: earlier rules win ties, so
# the more specific / urgent roles are listed before generic ones. Every rule's
# keywords must be unique to that rule where possible so a task routes cleanly.
ROUTE_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("sql injection", "secret leak", "vulnerab", "security audit", "xss", "csrf",
      "zero-day", "exploit", "cve", "xavfsizlik", "zaiflik", "audit", "hujum",
      "безопасность", "уязвимость"), "security"),
    (("changelog", "release notes", "what changed", "o'zgarishlar", "tarix",
      "история изменений"), "changelogger"),
    (("deploy", "ci/cd", "ci pipeline", "rollback", "staging", "production", "publish",
      "joylashtirish", "serverga yuklash", "деплой", "развертывание"), "deployer"),
    (("dependabot", "outdated package", "upgrade package", "update library", "bump version",
      "requirements.txt", "package.json", "dependency", "dependencies",
      "kutubxona yangilash", "paketlar", "bog'liqlik", "зависимости", "обновить пакет"), "dependency_updater"),
    (("write tests", "add tests", "unit tests", "integration tests", "test coverage",
      "test writer", "test yoz", "testlar yozish", "unit test", "написать тесты"), "test_writer"),
    (("run the tests", "run tests", "verify", "pass/fail", "does it pass", "run the suite",
      "testlarni ishga tushir", "tekshir", "test qil", "sinov", "запустить тесты", "проверить тесты"), "tester"),
    (("summarize", "summary", "condense", "shorten", "recap", "too long",
      "qisqartir", "xulosa", "umumlashtir", "qisqacha mazmun", "резюмировать", "кратко"), "summarizer"),
    (("remember", "memory vault", "save memory", "recall", "convention", "decision log",
      "architecture decision", "remember that", "eslab qol", "xotiraga saqla", "eslatma",
      "запомнить", "сохранить в память"), "memory_keeper"),
    (("token spend", "token usage", "cost", "budget", "how much did", "spend", "watcher",
      "xarajat", "narx", "token narxi", "стоимость", "расходы"), "cost_watcher"),
    (("triage", "classify error", "error severity", "critical or minor", "error routing",
      "saralash", "xatolik darajasi", "сортировка ошибок"), "triager"),
    (("readme", "api docs", "documentation", "docstrings", "update the docs",
      "doc writer", "hujjat", "qo'llanma", "dokumentatsiya", "документация", "инструкция"), "doc_writer"),
    (("routing", "which agent", "should handle", "dispatch", "intent router",
      "who does this", "yo'naltir", "qaysi agent", "marshrut", "маршрутизация"), "router"),
    (("review", "code review", "critic", "check my code", "is this correct", "quality",
      "kodni ko'rib chiq", "taqriz", "tekshirib ber", "ревью кода"), "reviewer"),
    (("plan", "strategy", "steps to", "how to", "roadmap",
      "reja", "rejalashtir", "strategiya", "qadamlar", "план", "спланировать"), "planner"),
    (("research", "find out", "what is", "who is", "search the web", "deep search",
      "qidir", "tadqiq", "ma'lumot top", "internetdan qidir", "исследовать", "найти информацию"), "researcher"),
    (("implement", "fix the bug", "refactor", "write code", "add feature", "convert",
      "bug in", "kod yoz", "xatoni to'g'irla", "funksiya yarat", "dastur yoz", "tuzat",
      "написать код", "исправить ошибку"), "coder"),
)


def _name(task: str | None) -> str:
    return str(task or "").strip().lower()


def _matched_keywords(task: str | None) -> list[tuple[str, str]]:
    """All (role, keyword) hits for a task, in rule order."""
    lowered = _name(task)
    out: list[tuple[str, str]] = []
    for keywords, role in ROUTE_RULES:
        for kw in keywords:
            if kw in lowered:
                out.append((role, kw))
                break  # one keyword per rule is enough to score it
    return out


def route_intent(task: str | None) -> IntentRoute:
    """Decide which staff role(s) should handle `task`.

    Deterministic keyword scoring:
    - primary role = highest hit count, ties broken by rule order;
    - supporting roles = the other matched roles (deduped, capped at 3),
      so the parent can fan out a parallel team;
    - empty / unmatched input -> generalist (never raises).
    """
    if not _name(task):
        return IntentRoute(
            primary_role="generalist",
            reason="Empty task fell back to the generalist role.",
        )
    matches = _matched_keywords(task)
    if not matches:
        return IntentRoute(
            primary_role="generalist",
            reason="No specialist keywords matched; fell back to the generalist role.",
        )
    # Group hits per role, keep first-seen (rule order) for tie-breaks.
    grouped: dict[str, list[int]] = {}  # role -> [hits, first_rule_index]
    for rule_idx, (role, _kw) in enumerate(matches):
        entry = grouped.setdefault(role, [0, rule_idx])
        entry[0] += 1
    scored = sorted(
        ((role, hits, rule_idx) for role, (hits, rule_idx) in grouped.items()),
        key=lambda row: (-row[1], row[2]),
    )
    primary = scored[0][0]
    supporting = tuple(
        row[0] for row in scored[1:] if row[0] != "generalist"
    )[:3]
    reasons = ", ".join(f"{r} via '{kw}'" for r, kw in matches)
    return IntentRoute(
        primary_role=primary,
        supporting_roles=supporting,
        reason=f"Matched keywords: {reasons}.",
    )