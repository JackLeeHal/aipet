import importlib
import pkgutil
import inspect
import os
from .base import Skill

class SkillLoader:
    def __init__(self, bus):
        self.bus = bus

    def load_skills(self):
        skills = []
        # Assuming we are in desktop_aipet.src.skills package
        skills_pkg = 'desktop_aipet.src.skills'
        skills_path = os.path.dirname(__file__)

        # Iterate over all items in the skills directory
        for _, name, ispkg in pkgutil.iter_modules([skills_path]):
            # We are looking for subdirectories mainly, but also .py files (legacy support if needed)

            full_name = f"{skills_pkg}.{name}"
            try:
                module = importlib.import_module(full_name)
                skills.extend(self._scan_module_for_skills(module))

                # If it is a package, it might have the skill code in a submodule like 'skill.py', 'handler.py', or '{name}.py'
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
                    # Dependency injection based on argument names
                    kwargs = {}
                    if 'bus' in sig.parameters:
                        kwargs['bus'] = self.bus

                    instance = attr(**kwargs)
                    found.append(instance)
                except Exception as e:
                    # Only report if it's not a typical "abstract class instantiation" error
                    # But Skill subclasses should be concrete
                    print(f"Error instantiating skill class {attr_name} in {module.__name__}: {e}")
        return found
