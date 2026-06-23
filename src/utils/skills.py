import os
import glob

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")

def _parse_frontmatter(filepath: str) -> dict:
    """Parses simple YAML frontmatter from a markdown file."""
    metadata = {}
    content_lines = []
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
        
    in_frontmatter = False
    frontmatter_done = False
    
    for line in lines:
        stripped = line.strip()
        if not frontmatter_done and stripped == "---":
            if not in_frontmatter:
                in_frontmatter = True
            else:
                in_frontmatter = False
                frontmatter_done = True
            continue
            
        if in_frontmatter:
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                metadata[key.strip()] = value.strip()
        else:
            if frontmatter_done or not in_frontmatter:
                content_lines.append(line)
                
    return {
        "metadata": metadata,
        "content": "".join(content_lines).strip()
    }

def get_all_skills() -> dict:
    """Returns a dictionary of skill_name -> (summary, content)."""
    skills = {}
    if not os.path.exists(SKILLS_DIR):
        return skills
        
    for filepath in glob.glob(os.path.join(SKILLS_DIR, "*.md")):
        parsed = _parse_frontmatter(filepath)
        name = parsed["metadata"].get("name")
        summary = parsed["metadata"].get("summary")
        if name and summary:
            skills[name] = {
                "summary": summary,
                "content": parsed["content"]
            }
    return skills

def get_skills_summary_string() -> str:
    """Returns a formatted string of all available skills and their summaries."""
    skills = get_all_skills()
    if not skills:
        return "No skills currently available."
        
    lines = []
    for name, data in skills.items():
        lines.append(f"- {name}: {data['summary']}")
    return "\n".join(lines)

def get_skill_content(skill_name: str) -> str:
    """Returns the full text of a skill given its name."""
    skills = get_all_skills()
    if skill_name in skills:
        return skills[skill_name]["content"]
    return f"Error: Skill '{skill_name}' not found. Available skills: {', '.join(skills.keys())}"
