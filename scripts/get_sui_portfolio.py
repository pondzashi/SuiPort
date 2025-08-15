import requests
import json

# =======================================================
# Configuration
# =======================================================
SUI_RPC_URL = 'https://fullnode.mainnet.sui.io:443'
SUI_ADDRESS = '0xa63ef51b8abf601fb40d8514050a8d5613c0509d4b36323dc4439ee6c69d704e'

# =======================================================
# RPC Helper Functions
# =======================================================
def rpc_call(method: str, params: list):
    """
    Makes a JSON-RPC call to the Sui full node.
    """
    payload = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': method,
        'params': params,
    }
    
    headers = {
        'Content-Type': 'application/json',
    }
    
    try:
        response = requests.post(SUI_RPC_URL, data=json.dumps(payload), headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        
        data = response.json()
        if 'error' in data:
            raise RuntimeError(f"RPC error: {data['error']['message']}")
            
        return data['result']
        
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"HTTP request error: {e}")
    except json.JSONDecodeError:
        raise RuntimeError("Failed to parse JSON response from RPC")

def get_all_balances(address: str):
    """
    Retrieves all coin balances for a given address.
    """
    return rpc_call('suix_getAllBalances', [address])

def get_coin_metadata(coin_type: str):
    """
    Retrieves metadata (symbol, decimals) for a coin type.
    """
    return rpc_call('suix_getCoinMetadata', [coin_type])

# =======================================================
# Main Script Logic
# =======================================================
def main():
    print(f"Fetching portfolio for address: {SUI_ADDRESS}\n")
    
    try:
        # Step 1: Get all coin balances
        balances = get_all_balances(SUI_ADDRESS)
        
        # Step 2: Iterate through balances to get metadata and format
        if not balances:
            print("No coins found in the portfolio.")
            return

        print(f"{'Symbol':<10} {'Balance (Human)':<20} {'Coin Type'}")
        print("-" * 60)

        for b in balances:
            coin_type = b.get('coinType')
            raw_balance = int(b.get('totalBalance', '0'))
            
            # Step 3: Get coin metadata for a user-friendly view
            meta = get_coin_metadata(coin_type)
            symbol = meta.get('symbol', 'N/A')
            decimals = int(meta.get('decimals', 0))
            
            # Convert raw balance to a human-readable format
            human_balance = raw_balance / (10 ** decimals)

            print(f"{symbol:<10} {human_balance:<20.8f} {coin_type}")
            
    except RuntimeError as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    # You need to have the `requests` library installed. 
    # If not, run: pip install requests
    main()
