import requests
from .base import IntegrationClient

class Trading212Client(IntegrationClient):
    def get_balance(self):
        # URLs
        LIVE_URL = "https://live.trading212.com/api/v0/"
        DEMO_URL = "https://demo.trading212.com/api/v0/"
        
        # Use HTTP Basic Auth with api_key as username and api_secret as password
        auth = (self.api_key, self.api_secret) if self.api_secret else None
        
        def fetch_from(base_url):
            try:
                response = requests.get(
                    f"{base_url}equity/account/summary",
                    auth=auth
                )
                if response.status_code == 200:
                    return float(response.json().get('totalValue', 0.0))
                return None
            except:
                return None

        # Try Live first
        balance = fetch_from(LIVE_URL)
        if balance is not None:
            return balance
            
        # Try Demo if Live failed
        balance = fetch_from(DEMO_URL)
        if balance is not None:
            return balance
            
        print("T212 Error: Could not fetch balance from Live or Demo.")
        return 0.0
