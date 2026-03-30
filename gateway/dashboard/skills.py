"""
Dashboard skills handlers -- view, toggle, and configure installed skills.

Provides:
- /settings/skills -- card grid of all skills grouped by category
- /settings/skills/{skill_name}/toggle -- enable/disable a skill
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import aiohttp_jinja2
    from aiohttp import web
except ImportError:
    pass


def _render_skills(request, flash=None):
    """Build skills tab context and render template. Synchronous -- do NOT await."""
    from hermes_cli.config import load_config, is_managed
    from hermes_cli.skills_config import get_disabled_skills

    config = load_config()
    managed = is_managed()
    disabled = get_disabled_skills(config)

    # Deferred import to avoid tool registry chain (Pitfall 4)
    from tools.skills_tool import _find_all_skills
    all_skills = _find_all_skills(skip_disabled=False)

    # Group by category and mark enabled/disabled
    categories = {}
    for skill in all_skills:
        cat = skill.get("category") or "uncategorized"
        if cat not in categories:
            categories[cat] = []
        categories[cat].append({
            "name": skill.get("name", "unknown"),
            "description": skill.get("description", ""),
            "enabled": skill.get("name", "") not in disabled,
            "settings": skill.get("settings", None),
        })

    # Sort categories alphabetically, skills within each category alphabetically
    sorted_categories = []
    for cat_name in sorted(categories.keys()):
        skills_in_cat = sorted(categories[cat_name], key=lambda s: s["name"])
        sorted_categories.append({"name": cat_name, "skills": skills_in_cat})

    return aiohttp_jinja2.render_template("settings/_skills.html", request, {
        "categories": sorted_categories,
        "managed": managed,
        "flash": flash,
        "total_skills": len(all_skills),
        "enabled_count": sum(1 for s in all_skills if s.get("name", "") not in disabled),
    })


async def handle_skills_tab(request):
    """GET /settings/skills -- render the Skills tab."""
    return _render_skills(request)


async def handle_skill_toggle(request):
    """POST /settings/skills/{skill_name}/toggle -- enable/disable a skill."""
    from hermes_cli.config import load_config, is_managed
    from hermes_cli.skills_config import get_disabled_skills, save_disabled_skills

    skill_name = request.match_info["skill_name"]

    if is_managed():
        return _render_skills(request, flash="error:Configuration is managed by NixOS/Enclava.")

    async with request.app["config_lock"]:
        config = load_config()
        disabled = get_disabled_skills(config)

        if skill_name in disabled:
            disabled.discard(skill_name)
            action = "enabled"
        else:
            disabled.add(skill_name)
            action = "disabled"

        save_disabled_skills(config, disabled)

    return _render_skills(request, flash="success:Skill '%s' %s." % (skill_name, action))
