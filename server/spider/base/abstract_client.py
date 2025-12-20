from abc import ABC, abstractmethod

class AbstractClient(ABC):
    @abstractmethod
    def get(self, url: str) -> str:
        pass

    @abstractmethod
    def close(self):
        pass