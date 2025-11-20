class CurrencyConverter:
    # Static rates for now (Base: USD)
    RATES = {
        'USD': 1.0,
        'EUR': 0.92,  # 1 USD = 0.92 EUR
        'MKD': 56.5   # 1 USD = 56.5 MKD
    }

    SYMBOLS = {
        'USD': '$',
        'EUR': '€',
        'MKD': 'den'
    }

    @staticmethod
    def convert(amount, from_currency, to_currency):
        """
        Convert amount from one currency to another.
        """
        if from_currency == to_currency:
            return amount
        
        # Convert to USD first
        usd_amount = amount / CurrencyConverter.RATES.get(from_currency, 1.0)
        
        # Convert from USD to target currency
        target_amount = usd_amount * CurrencyConverter.RATES.get(to_currency, 1.0)
        
        return round(target_amount, 2)

    @staticmethod
    def get_symbol(currency):
        return CurrencyConverter.SYMBOLS.get(currency, currency)
