import base58
import yaml
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import blake3
import time
import argparse
import uuid
import requests  
from flask import Flask, request

app = Flask(__name__)

class Wallet:
    def __init__(self, client_id, config_file=None):
        self.client_id = client_id
        self.config_file = 'config.yaml'
        self.key_file = f'dsc-key-cl{client_id}.yaml'

    def run(self, args):
        print(f"Running for client_id: {self.client_id}")
        if args.operation == "create":
            self.create_wallet()
        elif args.operation == "key":
            self.display_keys()
        elif args.operation == "balance":
            self.get_balance()
        elif args.operation == "send":
            amount = input("Enter the amount to send: ")
            recipient_address = input("Enter the recipient address: ")
            self.send_transaction(amount, recipient_address)
        elif args.operation == "transaction":
            transaction_id = input("Enter the transaction ID: ")
            self.check_transaction_status(transaction_id)
        elif args.operation == "transactions":
            self.list_transactions()
        elif args.operation == "help":
            self.print_help()
        else:
            print("Invalid operation. Use 'python wallet.py help' for supported operations.")

    def read_config(self):
        with open(self.config_file, "r") as file:
            config = yaml.safe_load(file)
        return config

    def create_wallet(self):
       
        if self.wallet_exists():
            print(f"Wallet already exists at dsc-key-{self.client_id}.yaml, wallet create aborted")
            return

        
        private_key, public_key = self.generate_key_pair()

       
        print("Wallet created successfully.")
        self.save_keys(public_key, private_key)

        print(f"Saved public key to config.yaml and private key to dsc-key-{self.client_id}.yaml in local folder")

    def display_keys(self):
        try:
            with open(self.key_file, "r") as file:
                keys = yaml.safe_load(file)
                if keys:
                    print(f"DSC Public Address: {keys['public_key']}")
                    print(f"DSC Private Address: {keys['private_key']}")
                else:
                    print("Error in finding key information.")
        except FileNotFoundError:
            print("Error in finding key information. Run `./dsc wallet create` to create a wallet.")

    def generate_key_pair(self):
        
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        ).decode('utf-8')

        
        private_key = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')

        return private_key, public_key

    def save_keys(self, public_key, private_key):
        
        hashed_public_key = self.hash_data(public_key.encode())
        hashed_private_key = self.hash_data(private_key.encode())

        keys = {"public_key": hashed_public_key, "private_key": hashed_private_key}

        
        with open(self.key_file, "w") as file:
            yaml.dump(keys, file)

       
        try:
            with open(self.config_file, 'r') as file:
                config = yaml.safe_load(file) or {}
        except FileNotFoundError:
            config = {}

       
        config.setdefault('wallet', {})['public_key'] = hashed_public_key

        
        with open(self.config_file, 'w') as file:
            yaml.dump(config, file)
        
        print(f"DSC Public Address: {hashed_public_key}")
        print(f"DSC Private Address: {hashed_private_key}")

    def wallet_exists(self):
        try:
            with open(self.key_file, "r") as file:
                keys = yaml.safe_load(file)
                print("Content of keys:", keys)  
                return keys is not None
        except FileNotFoundError:
            return False

    def hash_data(self, data):
        
        h = blake3.blake3()
        h.update(data)
        return h.hexdigest()

    def get_balance(self):
        config = self.read_config()
        address = config['public_key']
        balance = self.contact_blockchain_server_for_balance(address)
        return balance

    def send_transaction(self, amount, recipient_address):
         
        balance = self.get_balance()
        amount = float(amount)
        if amount > balance:
            print(f"Insufficient funds. Available balance is {balance} coins.")
            return
        
        config = self.read_config()
        transaction_id = self.create_transaction_id()
        timestamp = time.time()

        # Create a transaction object
        transaction = {
            'sender': config['public_key'],
            'recipient': recipient_address,
            'value': amount,
            'timestamp': timestamp,
            'tx_id': transaction_id,
            'status': "submitted"
        }

        
        self.submit_transaction_to_pool(transaction)

        print(f"Created transaction {transaction_id}, Sending {amount} coins to {recipient_address}")

        
        while transaction['status'] != 'confirmed':
            
            
            transaction['status'] = self.check_transaction_status(transaction_id)
            time.sleep(6)

        print(f"Transaction {transaction['tx_id']} status [confirmed]")

    def submit_transaction_to_pool(self, transaction):
       
        config = self.read_config()
        pool_server_address = config['pool']['server_address']

        try:
            response = requests.post(f"{pool_server_address}/submit_transaction", json=transaction)
            if response.status_code == 200:
                print("Transaction submitted successfully to the pool.")
            else:
                print(f"Failed to submit transaction: {response.text}")
        except requests.RequestException as e:
            print(f"Error submitting transaction to the pool: {e}")

    def check_transaction_status(self, transaction_id):
        config = self.read_config()
        pool_server_address = config['pool']['server_address']

        try:
            response = requests.get(f"{pool_server_address}/transaction_status", params={'id': transaction_id})
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                print(f"Transaction {transaction_id} status [{status}]")

                if status == "unknown":
                    
                    return self.check_blockchain_for_transaction_status(transaction_id)
                else:
                    return status
            else:
                print(f"Failed to get transaction status for {transaction_id}: {response.text}")
                return "error"
        except requests.RequestException as e:
            print(f"Error contacting mining pool for transaction {transaction_id}: {str(e)}")
            return "error"

    def list_transactions(self):
        transactions = self.contact_pool_for_transactions()

        print("DSC Wallet transactions:")
        for transaction in transactions:
            print(transaction)

    def contact_pool_for_transactions(self):
        
        try:
            config = self.read_config()
            pool_server_address = config['pool']['server_address']
            public_key = config['public_key']

            response = requests.get(f"{pool_server_address}/list_transactions", params={'public_key': public_key})
            if response.status_code == 200:
                return response.json()  # Assuming transactions are returned in JSON format
            else:
                print(f"Failed to retrieve transactions: {response.text}")
                return []
        except requests.RequestException as e:
            print(f"Error contacting mining pool: {str(e)}")
            return []

    def contact_blockchain_server_for_balance(self, address):
        try:
            config = self.read_config()
            blockchain_address = config['blockchain']['server_address']

            
            response = requests.get(f"{blockchain_address}/get_balance", params={'wallet_address': address})

            if response.status_code == 200:
                data = response.json()
                balance = data.get("balance", 0.0)
                block_number = data.get("block_id", 0)
                print(f"DSC Wallet balance: {balance} coins at block {block_number}")
                return balance
            else:
                print("Unable to retrieve balance. Please try again later.")
                return 0.0
        except requests.RequestException as e:
            print(f"Error contacting blockchain server: {str(e)}")
            print("Error occurred while retrieving balance.")

    def check_blockchain_for_transaction_status(self, transaction_id):
        config = self.read_config()
        blockchain_server_address = config['blockchain']['server_address']

        try:
            response = requests.get(f"{blockchain_server_address}/transaction_status", params={'id': transaction_id})
            if response.status_code == 200:
                try:
                    data = response.json()
                    status = data.get("status", "unknown")
                except ValueError:  
                    status = "unknown"
                print(f"Transaction {transaction_id} status [{status}]")
                return status
            else:
                print(f"Failed to get blockchain transaction status for {transaction_id}: {response.text}")
                return "unknown"
        except requests.RequestException as e:
            print(f"Error contacting blockchain server for transaction {transaction_id}: {str(e)}")
            return "unknown"


    def create_transaction_id(self):
        # creating a transaction ID
        
        return str(uuid.uuid4())

    def print_help(self):
        print("DSC: DataSys Coin Blockchain v1.0")
        print("Help menu for Wallet, supported operations:")
        print("./dsc wallet help")
        print("./dsc wallet create")
        print("./dsc wallet key")
        print("./dsc wallet balance")
        print("./dsc wallet send <amount> <address>")
        print("./dsc wallet transaction <ID>")
        print("./dsc wallet transactions")

def main():
    parser = argparse.ArgumentParser(description="Wallet operations")
    parser.add_argument("operation", nargs="?", default="create", help="Supported operations: create, key, balance, send, transaction, transactions, help")
    args = parser.parse_args()

    client_id = 1
    wallet = Wallet(client_id=client_id)
    wallet.run(args)

if __name__ == "__main__":
    main()
