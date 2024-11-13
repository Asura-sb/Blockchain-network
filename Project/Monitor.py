import requests
import yaml

def get_blockchain_stats(blockchain_url):
    header_response = requests.get(f"{blockchain_url}/get_latest_block_header")
    if header_response.status_code == 200:
        last_block_header = header_response.json()
    else:
        last_block_header = "Error fetching last block header"

    wallet_balance_response = requests.get(f"{blockchain_url}/get_all_balances")
    if wallet_balance_response.status_code == 200:
        wallet_balances = wallet_balance_response.json()
        unique_wallet_addresses = len(wallet_balances)
        total_coins = sum(wallet_balances.values())
    else:
        unique_wallet_addresses = "Error fetching wallet addresses"
        total_coins = "Error fetching total coins"

    return {
        "Last Block Header": last_block_header,
        "Unique Wallet Addresses": unique_wallet_addresses,
        "Total Coins in Circulation": total_coins
    }

def get_pool_stats(pool_url):
    transactions_response = requests.get(f"{pool_url}/get_transaction_counts")
    if transactions_response.status_code == 200:
        transaction_counts = transactions_response.json()
    else:
        transaction_counts = "Error fetching transaction counts"

    return transaction_counts

def get_metronome_stats(metronome_url):
    validators_response = requests.get(f"{metronome_url}/get_validator_stats")
    if validators_response.status_code == 200:
        validator_stats = validators_response.json()
    else:
        validator_stats = "Error fetching validator stats"

    return validator_stats

def display_stats(title, stats):
    print(f"\n{title}:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

def main():
    with open('config.yaml', "r") as file:
        config = yaml.safe_load(file)
    blockchain_url = config['blockchain']['server_address'] 
    pool_url = config['pool']['server_address']
    metronome_url = config['metronome']['server_address']

    blockchain_stats = get_blockchain_stats(blockchain_url)
    pool_stats = get_pool_stats(pool_url)
    metronome_stats = get_metronome_stats(metronome_url)

    display_stats("Blockchain Stats", blockchain_stats)
    display_stats("Pool Stats", pool_stats)
    display_stats("Metronome Stats", metronome_stats)

if __name__ == "__main__":
    main()
