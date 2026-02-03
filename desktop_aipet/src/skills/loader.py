import importlib
import pkgutil
import inspect
import os
import re
from pathlib import Path
from .base import Skill

class SkillLoader:
    def __init__(self, bus):
        self.bus = bus
        self.skills_path = Path(os.path.dirname(__file__))

    def load_skills(self):
        """Load Python-class based skills (Tools)"""
        skills = []
        skills_pkg = 'desktop_aipet.src.skills'

        # Iterate over all items in the skills directory
        for _, name, ispkg in pkgutil.iter_modules([str(self.skills_path)]):
            full_name = f"{skills_pkg}.{name}"
            try:
                module = importlib.import_module(full_name)
                skills.extend(self._scan_module_for_skills(module))

                if ispkg:
                    possible_submodules = ['skill', 'handler', name]
                    for sub in possible_submodules:
                        try:
                            sub_module_name = f"{full_name}.{sub}"
                            sub_module = importlib.import_module(sub_module_name)
                            skills.extend(self._scan_module_for_skills(sub_module))
                        except ImportError:
                            continue
            except Exception as e:
                print(f"Failed to load skill module {name}: {e}")

        # Deduplicate skills by name
        unique_skills = {}
        for skill in skills:
            if skill.name not in unique_skills:
                unique_skills[skill.name] = skill

        return list(unique_skills.values())

    def _scan_module_for_skills(self, module):
        found = []
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (inspect.isclass(attr) and
                issubclass(attr, Skill) and
                attr is not Skill):

                try:
                    sig = inspect.signature(attr.__init__)
                    kwargs = {}
                    if 'bus' in sig.parameters:
                        kwargs['bus'] = self.bus

                    instance = attr(**kwargs)
                    found.append(instance)
                except Exception as e:
                    print(f"Error instantiating skill class {attr_name} in {module.__name__}: {e}")
        return found

    def get_skills_context_prompt(self) -> str:
        """
        Generate a system prompt text describing available instruction-based skills (Markdown).
        This mimics the nanobot/anthropic approach of letting the agent know what skills are available
        and where they are located.
        """
        skills_info = []

        for skill_dir in self.skills_path.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    try:
                        content = skill_file.read_text(encoding="utf-8")
                        meta = self._parse_frontmatter(content)
                        name = meta.get('name', skill_dir.name)
                        desc = meta.get('description', 'No description provided.')

                        # We provide the path so the agent can inspect the skill if needed,
                        # or we can rely on the agent knowing it can import scripts from this path
                        # via PythonExecutionSkill.
                        # Important: The PythonExecutionSkill adds the skills parent dir to sys.path,
                        # so scripts can be imported like `from docx.scripts.document import Document`.

                        skill_entry = f"""
<skill>
    <name>{name}</name>
    <description>{desc}</description>
    <path>{skill_dir}</path>
    <instructions>
        This skill provides Python scripts and tools. You can use the 'execute_python' tool to import and use them.
        Example: `from {skill_dir.name}.scripts import ...`
        Refer to {skill_file} for detailed usage instructions.
    </instructions>
</skill>
"""
                        skills_info.append(skill_entry)
                    except Exception as e:
                        print(f"Error reading skill {skill_dir}: {e}")

        if not skills_info:
            return ""

        return "<available_skills>\n" + "".join(skills_info) + "\n</available_skills>"

    def _parse_frontmatter(self, content: str) -> dict:
        """Simple YAML frontmatter parser."""
        if content.startswith("---"):
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if match:
                metadata = {}
                for line in match.group(1).split("\n"):
                    if ":" in line:
                        parts = line.split(":", 1)
                        key = parts[0].strip()
                        value = parts[1].strip().strip('"\'')
                        metadata[key] = value
                return metadata
        return {}
