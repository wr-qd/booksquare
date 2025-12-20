from abc import ABC, abstractmethod
from typing import Dict

class AbstractStore(ABC):
    @abstractmethod
    def save_comment(self, data: Dict):
        pass