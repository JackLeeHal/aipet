import asyncio
import os
import sys

sys.path.append(os.getcwd())

from desktop_aipet.src.skills.loader import SkillLoader
from desktop_aipet.src.bus.event_bus import EventBus

async def main():
    bus = EventBus()
    loader = SkillLoader(bus)
    skills = loader.load_skills()

    for s in skills:
        schema = s.parameters
        print(f"Tool: {s.name}")
        if schema.get("function", {}).get("name") is None:
            print(f"  -> WARNING: name is None in schema!")
            print(schema)

if __name__ == "__main__":
    asyncio.run(main())
