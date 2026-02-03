import json
import asyncio
from typing import Dict, List, Any
from .base import Skill

class SkillRegistry:
    def __init__(self):
        self.skills: Dict[str, Skill] = {}

    def register(self, skill: Skill):
        self.skills[skill.name] = skill

    def get_schemas(self):
        # Return list of schemas in the format OpenAI expects
        return [s.parameters for s in self.skills.values()]

    async def execute(self, name: str, arguments_json: str) -> str:
        if name in self.skills:
            try:
                args = json.loads(arguments_json)
                return await self.skills[name].execute(**args)
            except Exception as e:
                return f"Error executing tool {name}: {str(e)}"
        return f"Tool {name} not found."
