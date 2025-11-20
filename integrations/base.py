from abc import ABC, abstractmethod

class IntegrationClient(ABC):
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret

    @abstractmethod
    def get_balance(self):
        """Returns the total equity in USD."""
        pass
