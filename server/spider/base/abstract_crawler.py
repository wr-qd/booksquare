from abc import ABC
from typing import List, Dict

class AbstractCrawler(ABC):
    def __init__(self):
        self.client = None
        self.store = None

    def start(self):
        pass

    def login(self):
        pass

    def fetch_data(self, query: str) -> List[Dict]:
        pass

    def parse_data(self, raw_data: Dict) -> Dict:
        pass

    def save_data(self, parsed_data: Dict):
        pass

    def close(self):
        pass