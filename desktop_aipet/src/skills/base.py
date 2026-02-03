from abc import ABC, abstractmethod
from typing import Any, Dict

class Skill(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """JSON Schema for parameters"""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        pass
