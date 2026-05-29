
# Skill loader: On-demand knowledge injection.

# Skills are markdown files (SKILL.md) with YAML frontmatter that describe verification workflows. 
# They are loaded into the LLM context only when relevant, not upfront. 
# This is the primary context management mechanism. Pattern from: learn-claude-code/docs/en/s05-skill-loading.md

import yaml
from pathlib import Path    

# Load and serve skills from a directory of SKILL.md files.
class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills: dict[str, dict] = {}
        self._load_all(skills_dir)

    # Scan for SKILL.md files and index them.
    def _load_all(self, skills_dir: Path):
        if not skills_dir.exists():
            return
        for skill_file in sorted(skills_dir.rglob("SKILL.md")):
            text = skill_file.read_text()
            meta, body = self._parse_frontmatter(text)
            name = meta.get("name", skill_file.parent.name)
            self.skills[name] = {
                "meta": meta,
                "body": body,
                "path": str(skill_file),
            }

    # Parse YAML frontmatter from a SKILL.md file.
    def _parse_frontmatter(self, text: str) -> tuple[dict, str]:
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                try:
                    meta = yaml.safe_load(parts[1]) or {}
                except yaml.YAMLError:
                    meta = {}
                body = parts[2].strip()
                return meta, body
        return {}, text

    # Return short descriptions for the system prompt (Layer 1 — cheap).
    def get_descriptions(self) -> str:
        lines = []
        for name, skill in self.skills.items():
            desc = skill["meta"].get("description", "No description")
            lines.append(f"  - {name}: {desc}")
        return "\n".join(lines)

    # Return the full body of a skill (Layer 2 — on demand, expensive).
    def get_content(self, name: str) -> str:
        skill = self.skills.get(name)
        if not skill:
            available = ", ".join(self.skills.keys())
            return f"Error: Unknown skill '{name}'. Available: {available}"
        return f"<skill name=\"{name}\">\n{skill['body']}\n</skill>"

    # Return list of available skill names.
    def list_skills(self) -> list[str]:
        return list(self.skills.keys())
