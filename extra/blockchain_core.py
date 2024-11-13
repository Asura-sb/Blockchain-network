import time
import uuid
import threading
from blake3 import blake3
import requests
import yaml
class Transaction:
    def __init__(self, sender, recipient, value, timestamp, tx_id, status):
        self.sender = sender
        self.recipient = recipient
        self.value = value
        self.timestamp = timestamp
        self.tx_id = tx_id
        self.status = status

    def to_dict(self):
        return {
            'sender': self.sender,
            'recipient': self.recipient,
            'value': self.value,
            'timestamp': self.timestamp,
            'tx_id': self.tx_id,
            'status': self.status
        }

class Block:
    def __init__(self, version, prev_block_hash, block_id, timestamp, difficulty_target, nonce, transactions, validator_id=None, fingerprint=None):
        self.version = version
        self.prev_block_hash = prev_block_hash
        self.block_id = block_id
        self.timestamp = timestamp
        self.difficulty_target = difficulty_target
        self.nonce = nonce
        self.transactions = transactions
        self.validator_id = validator_id
        self.validator_fingerprint = fingerprint

    def to_dict(self):
        return {
            'version': self.version,
            'prev_block_hash': self.prev_block_hash,
            'block_id': self.block_id,
            'timestamp': self.timestamp,
            'difficulty_target': self.difficulty_target,
            'nonce': self.nonce,
            'transactions': [tx.to_dict() for tx in self.transactions],
            'validator_id': self.validator_id,
            'validator_fingerprint': self.validator_fingerprint
        }

class Blockchain:
    def __init__(self, difficulty):
        self.chain = []
        self.address_balances = {}
        self.balance_lock = threading.Lock()
        self.difficulty = difficulty
        self.create_genesis_block()
        self.update_balances()

    def create_genesis_block(self):
        transactions = [Transaction("root", "genesis_recipient", 100, time.time(), str(uuid.uuid4()), "confirmed")]
        genesis_block = Block(1, "0" * 64, 1, time.time(), self.difficulty, 0, transactions, "Genesis", "Genesis")
        self.chain.append(genesis_block)

    def create_block(self, transactions, validator_id=None, fingerprint=None, nonce=0):
        last_block = self.chain[-1]
        version = 1
        prev_block_hash = self.hash_block(last_block)
        block_id = len(self.chain) + 1
        timestamp = time.time()
        difficulty_target = self.difficulty

        if nonce is None:
         nonce = 0  # Default value or handle it appropriately

        # Create a new block with the provided transactions
        new_block = Block(version, prev_block_hash, block_id, timestamp, difficulty_target, nonce, transactions, validator_id, fingerprint)

        # Update the status of each transaction in the block
        for tx in transactions:
              tx.status = "confirmed"  # Update the status attribute of each Transaction object
        if transactions:
              with open('config.yaml', "r") as file:
                  config = yaml.safe_load(file)
              pool_server_address = config['pool']['server_address']
              transactions_dict = [transaction.to_dict() for transaction in transactions]
              requests.post(f"{pool_server_address}/confirm_transactions", json=transactions_dict)
      
        # Append the new block to the blockchain
        self.chain.append(new_block)

        # Use threading to update balances
        update_thread = threading.Thread(target=self.update_balances)
        update_thread.start()
        update_thread.join()
        return new_block

    def hash_block(self, block):
        block_str = (
            str(block.version) +
            str(block.prev_block_hash) +
            str(block.block_id) +
            str(block.timestamp) +
            str(block.difficulty_target) +
            str(block.nonce) +
            ''.join([str(tx.to_dict()) for tx in block.transactions]) +
            str(block.validator_id or '') +
            str(block.validator_fingerprint or '')
        )
        return blake3(block_str.encode()).hexdigest()

    def update_balances(self):
        temp_balances = {}
        with self.balance_lock:
            for block in self.chain:
                for tx in block.transactions:
                    sender_balance = temp_balances.get(tx.sender, 0)
                    recipient_balance = temp_balances.get(tx.recipient, 0)
                    if tx.sender != "root":
                        temp_balances[tx.sender] = sender_balance - tx.value
                    temp_balances[tx.recipient] = recipient_balance + tx.value
            self.address_balances = temp_balances

    def get_latest_block_hash(self):
        if len(self.chain) > 0:
            latest_block = self.chain[-1]
            return self.hash_block(latest_block), latest_block.block_id
        else:
            return None, None

    def lookup_transaction_state(self, tx_id):
        for block in self.chain:
            for transaction in block.transactions:
                if transaction.tx_id == tx_id:
                    return transaction.status
        return "Transaction not found"

    def get_balance(self, address):
        with self.balance_lock:
            return self.address_balances.get(address, 0)

    def get_transactions_for_address(self, address):
        transactions = []
        for block in self.chain:
            for transaction in block.transactions:
                if transaction.sender == address or transaction.recipient == address:
                    transactions.append(transaction.to_dict())
        return transactions

    # Additional utility methods can be added here as needed
