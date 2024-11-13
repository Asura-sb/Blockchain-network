import time
import uuid
from blake3 import blake3
from flask import Flask, request, jsonify
import threading
import requests
import yaml

app = Flask(__name__)

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
    def update_status(self, new_status):
        self.status = new_status

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
            'fingerprint' : self.validator_fingerprint
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
        transactions = [Transaction("root", "02c6ba713d162063f53a105379c3127e18ca6a6392372a57aa5633327fb92cc0", 1024, time.time(), str(uuid.uuid4()), "confirmed")]
        genesis_block = Block(1, "0" * 64, 1, time.time(), self.difficulty, 0, transactions, "Genesis", "Genesis")
        self.chain.append(genesis_block)
        print("Genesis block created")
        self.print_blockchain_info()

    def create_block(self, transactions, validator_id=None, fingerprint=None, nonce=None):
      last_block = self.chain[-1]
      version = 1
      prev_block_hash = self.hash_block(last_block)
      block_id = len(self.chain) + 1
      timestamp = time.time()
      difficulty_target = self.difficulty

      
      if nonce is None:
         nonce = 0 

      
      new_block = Block(version, prev_block_hash, block_id, timestamp, difficulty_target, nonce, transactions, validator_id, fingerprint)

      
      for tx in transactions:
            tx.status = "confirmed"  
      if transactions:
            with open('config.yaml', "r") as file:
                config = yaml.safe_load(file)
            pool_server_address = config['pool']['server_address']
            transactions_dict = [transaction.to_dict() for transaction in transactions]
            requests.post(f"{pool_server_address}/confirm_transactions", json=transactions_dict)
      
      
      self.chain.append(new_block)

      
      update_thread = threading.Thread(target=self.update_balances)
      update_thread.start()
      update_thread.join()

      if validator_id and fingerprint:
          print(f"New block mined: Block ID {new_block.block_id}, Validator ID {validator_id}, Fingerprint {fingerprint}, Block Hash {self.hash_block(new_block)}")
      else:
          print(f"Empty block mined: Block ID {new_block.block_id}, Block Hash {self.hash_block(new_block)}")

      return new_block

    

    def get_latest_block_header(self):
        if len(self.chain) > 0:
            latest_block = self.chain[-1]
            return latest_block.to_dict()
        else:
            return None

    def lookup_transaction_state(self, tx_id):
        for block in self.chain:
            for transaction in block.transactions:
                if transaction.tx_id == tx_id:
                    return transaction.status
        return "Transaction not found"

    def update_balances(self):
        temp_balances = {}  

        for block in self.chain:
            for transaction in block.transactions:
                
                with self.balance_lock:  
                    sender_balance = temp_balances.get(transaction.sender, 0)
                    recipient_balance = temp_balances.get(transaction.recipient, 0)
                    if transaction.sender != "root":
                        temp_balances[transaction.sender] = sender_balance - transaction.value
                    temp_balances[transaction.recipient] = recipient_balance + transaction.value

        with self.balance_lock:
            self.address_balances = temp_balances  

    def get_balance(self, address):
        print(self.address_balances)
        return self.address_balances.get(address,0)

    def get_transactions_for_address(self, address):
        transactions = []
        for block in self.chain:
            for transaction in block.transactions:
                if transaction.sender == address or transaction.recipient == address:
                    transactions.append(transaction.to_dict())
        return transactions

    
    def get_latest_block_hash(self):
        if len(self.chain) > 0:
            latest_block = self.chain[-1]
            return self.hash_block(latest_block), latest_block.block_id
        else:
            return None, None
    
    def hash_block(self, block):
        block_str = (
            str(block.version) +
            str(block.prev_block_hash) +
            str(block.block_id) +  
            str(block.timestamp) +
            str(block.difficulty_target) +
            str(block.nonce) +
            ''.join([str(tx.to_dict()) for tx in block.transactions]) +
            str(block.validator_id) +  
            str(block.validator_fingerprint) 
        )
        return blake3(block_str.encode()).hexdigest()

    

    def print_blockchain_info(self):
        print(f"Blockchain now contains {len(self.chain)} blocks:")
        for block in self.chain:
            print(f"  Block ID: {block.block_id}, Hash: {self.hash_block(block)}")


blockchain = Blockchain(difficulty=20)

@staticmethod
@app.route('/get_difficulty', methods=['GET'])
def get_difficulty():
    global blockchain
    return jsonify({"difficulty": blockchain.difficulty}), 200


@staticmethod
@app.route('/get_latest_block_header', methods=['GET'])
def get_latest_block_header():
    global blockchain
    latest_block_header = blockchain.get_latest_block_header()
    if latest_block_header:
        return jsonify(latest_block_header), 200
    else:
        return jsonify({"error": "No blocks found in the chain"}), 404
    


@app.route('/get_all_balances', methods=['GET'])
def get_all_balances():
    global blockchain
    return jsonify(blockchain.address_balances), 200

@staticmethod
@app.route('/get_total_coins', methods=['GET'])
def get_total_coins():
    global blockchain
    total_coins = sum(blockchain.address_balances.values())
    return jsonify({"total_coins": total_coins}), 200


@staticmethod
@app.route('/transaction_status', methods=['GET'])
def get_transaction_status():
    tx_id = request.args.get('id')
    global blockchain
    for blk in blockchain.chain:
        for tx in blk.transactions:
            if tx.tx_id == tx_id:
                return jsonify(status=tx.status)
    return jsonify(status="unknown")

@staticmethod
@app.route('/lookup_transaction_state', methods=['GET'])
def lookup_transaction_state():
    global blockchain
    tx_id = request.args.get('tx_id')
    state = blockchain.lookup_transaction_state(tx_id)
    return jsonify({"transaction_state": state}), 200

@staticmethod
@app.route('/get_balance', methods=['GET'])
def get_balance():
    global blockchain
    address = request.args.get('wallet_address')
    balance = blockchain.get_balance(address)
    latest_block_id = blockchain.chain[-1].block_id if blockchain.chain else None
    return jsonify({"balance": balance, "block_id": latest_block_id}), 200

@staticmethod
@app.route('/get_transactions_for_address', methods=['GET'])
def get_transactions_for_address():
    global blockchain
    address = request.args.get('address')
    transactions = blockchain.get_transactions_for_address(address)
    return jsonify({"transactions": transactions}), 200

@staticmethod
@app.route('/mine_block', methods=['POST'])
def mine_block():
    global blockchain
    data = request.get_json()  

    
    if not isinstance(data.get('transactions', []), list):
        return jsonify({"error": "Invalid transaction format"}), 400

    transactions = []
    for tx_data in data.get('transactions', []):
        
        if not isinstance(tx_data, dict):
            return jsonify({"error": "Invalid transaction data format"}), 400
        try:
            transaction = Transaction(**tx_data)
            transactions.append(transaction)
        except TypeError as e:
            return jsonify({"error": f"Invalid transaction data: {str(e)}"}), 400

    validator_id = data.get('validator_id')
    fingerprint = data.get('fingerprint')
    nonce = data.get('nonce')
    new_block = blockchain.create_block(transactions, validator_id=validator_id, fingerprint=fingerprint)
    block_hash = blockchain.hash_block(new_block)
    block_id = new_block.block_id
    return jsonify({"message": "Block mined successfully", "block_hash": block_hash, "block_id": block_id}), 200


@staticmethod
@app.route('/get_latest_block_hash', methods=['GET'])
def get_latest_block_hash():
    global blockchain
    latest_block_hash, block_id = blockchain.get_latest_block_hash()
    if latest_block_hash:
        return jsonify({"latest_block_hash": latest_block_hash, "block_id": block_id}), 200
    else:
        return jsonify({"error": "No blocks found in the chain"}), 404


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5002)