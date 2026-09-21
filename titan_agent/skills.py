"""Skills system for TITAN AGENT (Hermes/ECC-class reusable workbooks).

Skills are markdown "playbooks" stored in `skills/*.md` with a small YAML-like
front-matter block:

    ---
    name: research-ops
    description: Multi-source research playbook with citation discipline.
    keywords: research, sources, citations, deep dive
    ---
    <full markdown guidance body>

The agent auto-loads relevant skills for a task (lexical keyword match against
the user's request) and can also pull any skill on demand via the `skill_load`
and `skills_list` tools — the same pattern Hermes uses with its skills catalog.
"""
import logging
import re
from pathlib import Path
from typing import Any

from .config import BASE_DIR

SKILLS_DIR = BASE_DIR / "skills"
SKILLS_DIR.mkdir(parents=True, exist_ok=True)

# Cap on how much skill text is injected into the system prompt so a task can
# never blow the context budget (skills are guides, not dumps).
MAX_SYSTEM_SKILL_CHARS = 1600
MAX_MATCHES_INJECTED = 2


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9_\-']*", str(text).lower()))


def _parse_front_matter(raw: str) -> dict[str, str] | None:
    """Extract the `---` front-matter block as a plain dict (name/description/keywords)."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", raw, re.DOTALL)
    if not m:
        return None
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip().lower()] = value.strip()
    return meta


class Skill:
    """A single skill: metadata plus the full markdown guidance body."""

    def __init__(self, name: str, description: str, keywords: str, body: str, source: Path | None = None):
        self.name = name
        self.description = description
        self.keywords = keywords
        self.body = body
        self.source = source

    def full_text(self) -> str:
        head = f"# {self.name}\n\n{self.description}\n"
        if self.keywords:
            head += f"\nKeywords: {self.keywords}\n"
        return head + "\n" + self.body.strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "keywords": self.keywords,
            "body_length": len(self.body),
        }


class SkillRegistry:
    """Loads and matches skills from the `skills/` directory (Hermes-style catalog)."""

    def __init__(self, skills_dir: Path = SKILLS_DIR):
        self.skills_dir = Path(skills_dir)
        self.skills: dict[str, Skill] = {}
        self.scan()

    def scan(self):
        """(Re)load every skill file found under the skills directory."""
        log = logging.getLogger(__name__)
        found: dict[str, Skill] = {}
        if self.skills_dir.exists():
            for fpath in sorted(self.skills_dir.glob("*")):
                if not fpath.is_file():
                    continue
                if fpath.suffix.lower() not in (".md", ".markdown"):
                    continue
                try:
                    raw = fpath.read_text(encoding="utf-8", errors="ignore")
                except OSError as e:
                    log.debug("Failed to read skill file %s: %s", fpath, e)
                    continue
                meta = _parse_front_matter(raw)
                body = re.sub(r"^---\s*\n.*?\n---\s*\n?", "", raw, flags=re.DOTALL).strip()
                if meta and meta.get("name"):
                    found[meta["name"]] = Skill(
                        name=meta["name"],
                        description=meta.get("description", ""),
                        keywords=meta.get("keywords", ""),
                        body=body or "(no guidance body yet)",
                        source=fpath,
                    )
        self.skills = found

    def list_skills(self) -> list[dict[str, Any]]:
        self.scan()
        return [s.to_dict() for s in self.skills.values()]

    def get_skill(self, name: str) -> Skill | None:
        self.scan()
        return self.skills.get(name)

    def find_matches(self, query: str, top_k: int = MAX_MATCHES_INJECTED) -> list[Skill]:
        """Rank skills by keyword overlap with the request (Hermes auto-skill-load)."""
        self.scan()
        q_tokens = _tokens(query) if query else set()
        if not q_tokens:
            return []
        ranked = []
        for skill in self.skills.values():
            hay = _tokens(f"{skill.name} {skill.description} {skill.keywords}")
            if not hay:
                continue
            hits = len(q_tokens & hay)
            if hits:
                name_tokens = _tokens(skill.name)
                name_hit = 1.0 if (q_tokens & name_tokens) else 0.0
                ranked.append((hits + name_hit, skill))
        ranked.sort(key=lambda r: -r[0])
        return [s for _, s in ranked[: max(top_k, 1)]]

    def build_system_block(self, query: str, top_k: int = MAX_MATCHES_INJECTED) -> str:
        """Markdown block with the most relevant skills, capped in size."""
        matches = self.find_matches(query, top_k=top_k)
        if not matches:
            return ""
        parts = ["\n### RELEVANT SKILL PLAYBOOKS (follow these for this task):"]
        budget = MAX_SYSTEM_SKILL_CHARS
        for skill in matches:
            block = f"\n#### Skill: {skill.name} — {skill.description}\n{skill.full_text()}\n"
            if len(block) > budget:
                block = block[:budget] + "\n...(skill truncated)"
            parts.append(block)
            budget -= len(block)
        return "\n".join(parts)