import threading
import blake3
from collections import OrderedDict
from flask import Flask, request, jsonify
from multiprocessing import Process
import yaml


app = Flask(__name__)
mining_pool = None  

def run_flask_app(port):
    app.run(host='0.0.0.0', port=port)

class MiningPool:
    def __init__(self, blockchain_address, flask_port):
        self.flask_port = flask_port
        self.blockchain_address = blockchain_address
        self.submitted_transactions = OrderedDict()
        self.unconfirmed_transactions = OrderedDict()
        self.lock = threading.Lock()

    def add_transaction(self, transaction):
        with self.lock:
            self.submitted_transactions[transaction['tx_id']] = transaction

    def start_pool(self):
        flask_process = Process(target=run_flask_app, args=(self.flask_port,))
        flask_process.start()
        print(f"Flask server running on port {self.flask_port}")

    def get_transaction_counts(self):
        with self.lock:
            return {
                "submitted_count": len(self.submitted_transactions),
                "unconfirmed_count": len(self.unconfirmed_transactions)
            }


with open('config.yaml', "r") as file:
    config = yaml.safe_load(file)
blockchain_address = config['blockchain']['server_address']
flask_port = 5005
mining_pool = MiningPool(blockchain_address, flask_port)

@app.route('/submit_transaction', methods=['POST'])
def submit_transaction():
    transaction = request.json
    mining_pool.add_transaction(transaction)
    return {"message": "Transaction added to the pool"}, 200

@app.route('/confirm_transactions', methods=['POST'])
def confirm_transactions():
    transactions_data = request.json 
    for tx_data in transactions_data:
        if tx_data['tx_id'] in mining_pool.unconfirmed_transactions:
            del mining_pool.unconfirmed_transactions[tx_data['tx_id']]
    # Return a valid response
    return "Transactions processed", 200  

@app.route('/transaction_status', methods=['GET'])
def transaction_status():
    tx_id = request.args.get('id')
    with mining_pool.lock:
        if tx_id in mining_pool.submitted_transactions:
            return {"status": "submitted"}, 200
        elif tx_id in mining_pool.unconfirmed_transactions:
            return {"status": "unconfirmed"}, 200
        else:
            return {"status": "unknown"}, 200

@app.route('/get_transactions', methods=['GET'])
def get_transactions():
    with mining_pool.lock:
        transactions = list(mining_pool.submitted_transactions.values())[:10]
        for tx in transactions:
            tx_id = tx['tx_id']
            mining_pool.unconfirmed_transactions[tx_id] = tx
            del mining_pool.submitted_transactions[tx_id]
    return jsonify(transactions), 200

@app.route('/list_transactions', methods=['GET'])
def list_transactions():
    public_key = request.args.get('public_key')
    if not public_key:
        return jsonify({"error": "Public key is required"}), 400

    with mining_pool.lock:
        all_transactions = list(mining_pool.submitted_transactions.values()) + \
                           list(mining_pool.unconfirmed_transactions.values())
        filtered_transactions = [txn for txn in all_transactions if txn.get('sender') == public_key]
    return jsonify(filtered_transactions), 200

@app.route('/get_transaction_counts', methods=['GET'])
def get_transaction_counts():
    return jsonify(mining_pool.get_transaction_counts()), 200


if __name__ == "__main__":
    mining_pool.start_pool()
