import threading
import time
import requests
from flask import Flask, request, jsonify
import yaml

app = Flask(__name__)

class Metronome:
    def __init__(self,blockchain_server,pool_server):
        self.blockchain_server = blockchain_server
        self.pool_server = pool_server
        self.block_generation_interval = 6 # seconds
        self.metronome_thread = threading.Thread(target=self._metronome_loop, daemon=True)
        self.is_running = False
        self.validators = {} 
        self.validator_statistics = {}  
        self.start()
    

    def _metronome_loop(self):
        while self.is_running:
            self.generate_and_process_block()
            time.sleep(self.block_generation_interval)

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.metronome_thread.start()
            print("Metronome started with 2 worker threads.")

    def stop(self):
        if self.is_running:
            self.is_running = False
            print("Metronome stopped.")

    def generate_and_process_block(self):
      raw_transactions = self.fetch_transactions_from_pool()
      transactions = self.format_transactions(raw_transactions) if raw_transactions else []

      winning_validator = self.select_winning_validator()
      if winning_validator:
          print(f"{time.strftime('%Y%m%d %H:%M:%S')} Validator {winning_validator} wins block.")
          validator_fingerprint = self.validators[winning_validator]['fingerprint']
          nonce = self.validator_statistics[winning_validator].get('nonce', 0)  # Get nonce from statistics
          block_data = {
              "transactions": transactions, 
              "validator_id": winning_validator, 
              "fingerprint": validator_fingerprint,
              "nonce": nonce  
          }
      else:
          print(f"{time.strftime('%Y%m%d %H:%M:%S')} No validators won the block. Creating empty block.")
          block_data = {"transactions": transactions}

      mine_response = requests.post(f"{self.blockchain_server}/mine_block", json=block_data)
      if mine_response.status_code == 200:
          response_data = mine_response.json()
          block_hash = response_data.get("block_hash")
          print(f"Block mined, hash: {block_hash}, added to blockchain.")
      else:
          print(f"Failed to mine block.")

    def format_transactions(self, raw_transactions):
        formatted_transactions = [] 
        for tx in raw_transactions:
            formatted_transaction = {
                'sender': tx.get('sender'),
                'recipient': tx.get('recipient'),
                'value': tx.get('value'),
                'timestamp': tx.get('timestamp'),
                'tx_id': tx.get('tx_id'),
                'status': 'unconfirmed'
            }
            formatted_transactions.append(formatted_transaction)
        return formatted_transactions
    
    def fetch_transactions_from_pool(self):
        try:
            response = requests.get(f"{self.pool_server}/get_transactions")
            return response.json() if response.status_code == 200 else []
        except Exception as e:
            print(f"Failed to fetch transactions from pool: {e}")
            return []

    def register_validator(self, validator_id, fingerprint):
        if validator_id not in self.validators:
            self.validators[validator_id] = {'fingerprint': fingerprint}
            print(f"Validator {validator_id} registered.")
        else:
            print(f"Validator {validator_id} is already registered.")

    def report_statistics(self, validator_id, proof_type, nonce, hash_rate):
        self.validator_statistics[validator_id] = {"proof_type": proof_type, "nonce": nonce, "hash_rate": hash_rate}

    def select_winning_validator(self):
        for validator_id, stats in self.validator_statistics.items():
            if self.is_proof_successful(stats):
                return validator_id
        return None

    def is_proof_successful(self, statistics):
        nonce = statistics.get('nonce')
        return nonce != -1
    
    def get_validator_stats(self):
       
        total_hashes = 0
        hash_rates = [stats['hash_rate'] for stats in self.validator_statistics.values()]
        for rate in hash_rates:
            total_hashes += rate

        return {
            "number_of_validators": len(self.validator_statistics),
            "hash_rates": hash_rates,
            "total_hashes_stored": total_hashes
        }



@app.route('/start_metronome', methods=['POST'])
def start_metronome_route():
    metronome.start()
    return jsonify({"message": "Metronome started."}), 200

@app.route('/stop_metronome', methods=['POST'])
def stop_metronome_route():
    metronome.stop()
    return jsonify({"message": "Metronome stopped."}), 200

@app.route('/register_validator', methods=['POST'])
def register_validator_route():
    data = request.json
    validator_id = data.get('validator_id')
    fingerprint = data.get('fingerprint')
    metronome.register_validator(validator_id, fingerprint)
    return jsonify({"message": f"Validator {validator_id} registered."}), 200

@app.route('/report_statistics', methods=['POST'])
def report_statistics_route():
    data = request.json
    validator_id = data.get('validator_id')
    proof_type = data.get('proof_type')
    nonce = data.get('nonce')
    hash_rate = data.get('hash_rate')
    metronome.report_statistics(validator_id, proof_type, nonce, hash_rate)
    return jsonify({"message": f"Statistics updated for validator {validator_id}."}), 200

@app.route('/get_validator_stats', methods=['GET'])
def get_validator_stats_route():
   
    stats = metronome.get_validator_stats()
    return jsonify(stats)

@app.route('/get_current_difficulty', methods=['GET'])
def get_current_difficulty():
    try:
        response = requests.get(f"{metronome.blockchain_server}/get_difficulty")
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({"error": "Failed to retrieve difficulty from blockchain"}), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    with open('config.yaml', "r") as file:
        config = yaml.safe_load(file)
    blockchain_server = config['blockchain']['server_address'] 
    pool_server = config['pool']['server_address']
    metronome = Metronome(blockchain_server,pool_server)
    app.run(host='0.0.0.0', port=5003)
    

