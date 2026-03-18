from abc import ABC, abstractmethod

class BaseCollector(ABC):
    def __init__(self, history):
        self.history = history

    @abstractmethod
    def fetch(self):
        """
        抓取数据，返回一个列表，每项格式为:
        {
            "title": str,
            "desc": str,
            "url": str (unique key),
            "stars": str (optional),
            "pub_time": str (optional),
            "picurl": str (optional)
        }
        """
        pass
