from pybit.unified_trading import HTTP
from .base import IntegrationClient

class BybitClient(IntegrationClient):
    def get_balance(self):
        try:
            session = HTTP(
                testnet=False, # Use Mainnet
                api_key=self.api_key,
                api_secret=self.api_secret
            )
            
            total_balance = 0.0

            def get_equity(account_type):
                try:
                    response = session.get_wallet_balance(accountType=account_type)
                    if response['retCode'] == 0 and response['result']['list']:
                        account_info = response['result']['list'][0]
                        
                        # For UNIFIED, use totalEquity
                        if account_type == "UNIFIED":
                            equity = float(account_info.get('totalEquity', 0.0))
                            print(f"Bybit UNIFIED totalEquity: {equity}")
                            return equity
                        
                        # For SPOT and others, sum coin USD values
                        equity = 0.0
                        for coin in account_info.get('coin', []):
                            coin_value = float(coin.get('usdValue', 0.0))
                            if coin_value > 0:
                                print(f"Bybit {account_type} {coin.get('coin', 'Unknown')}: {coin_value}")
                            equity += coin_value
                        
                        print(f"Bybit {account_type} total: {equity}")
                        return equity
                    else:
                        print(f"Bybit {account_type} returned retCode: {response.get('retCode', 'unknown')}")
                    return 0.0
                except Exception as e:
                    print(f"Bybit {account_type} Error: {e}")
                    return 0.0

            def get_fund_balance(account_type):
                """Get FUND account balance using get_coins_balance endpoint"""
                try:
                    # Get all coins in FUND account (without specifying coin)
                    response = session.get_coins_balance(accountType=account_type)
                    if response['retCode'] == 0:
                        fund_total = 0.0
                        for coin_data in response['result'].get('balance', []):
                            wallet_balance = float(coin_data.get('walletBalance', 0.0))
                            if wallet_balance > 0:
                                print(f"Bybit FUND {coin_data.get('coin', 'Unknown')}: {wallet_balance}")
                                # Note: This is in coin units, not USD. For accurate USD value,
                                # we'd need to convert using market prices, but for now we'll sum as-is
                                fund_total += wallet_balance
                        print(f"Bybit FUND total: {fund_total}")
                        return fund_total
                    else:
                        print(f"Bybit FUND returned retCode: {response.get('retCode', 'unknown')}")
                    return 0.0
                except Exception as e:
                    print(f"Bybit FUND Error: {e}")
                    return 0.0

            # Combine all account types
            total_balance += get_equity("UNIFIED")
            total_balance += get_equity("CONTRACT")
            total_balance += get_equity("SPOT")
            total_balance += get_fund_balance("SPOT")
            total_balance += get_fund_balance("CONTRACT")
            total_balance += get_fund_balance("UNIFIED")
            total_balance += get_fund_balance("OPTION")
            total_balance += get_fund_balance("INVESTMENT")
            total_balance += get_fund_balance("FUND")
            
            #SPOT, CONTRACT, UNIFIED, OPTION, INVESTMENT, FUND
            print(f"Bybit Total Balance: {total_balance}")
            return total_balance
        except Exception as e:
            print(f"Bybit Exception: {e}")
            return 0.0
