from flask import Flask, request, jsonify
from pool_core import MiningPool
import threading
from multiprocessing import Manager,Process, freeze_support
import yaml


def create_app(port, blockchain_address, shared_state):
    app = Flask(__name__)

    # Instantiate the mining pool with shared state
    mining_pool = MiningPool(blockchain_address, shared_state)

    # Define Flask routes
    @app.route('/submit_transaction', methods=['POST'])
    def submit_transaction():
        transaction = request.json
        mining_pool.add_transaction(transaction)
        return {"message": "Transaction added to the pool"}, 200

    @app.route('/confirm_transactions', methods=['POST'])
    def confirm_transactions():
        transactions_data = request.json
        mining_pool.confirm_transactions(transactions_data)
        return "Transactions processed", 200

    @app.route('/transaction_status', methods=['GET'])
    def transaction_status():
        tx_id = request.args.get('id')
        status = "unknown"
        if tx_id in mining_pool.submitted_transactions:
            status = "submitted"
        elif tx_id in mining_pool.unconfirmed_transactions:
            status = "unconfirmed"
        return jsonify({"status": status}), 200

    @app.route('/get_transactions', methods=['GET'])
    def get_transactions():
        transactions = mining_pool.get_transactions()
        return jsonify(transactions), 200

    @app.route('/list_transactions', methods=['GET'])
    def list_transactions():
        public_key = request.args.get('public_key')
        if not public_key:
            return jsonify({"error": "Public key is required"}), 400
        transactions = mining_pool.list_transactions_for_public_key(public_key)
        return jsonify(transactions), 200

    @app.route('/get_transaction_counts', methods=['GET'])
    def get_transaction_counts():
        return jsonify(mining_pool.get_transaction_counts()), 200

    return app

def run_app(port, blockchain_address, shared_state):
    app = create_app(port, blockchain_address, shared_state)
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def main():
    with open('config.yaml', "r") as file:
        config = yaml.safe_load(file)

    blockchain_address = config['blockchain']['server_address']

    # Define ports for each instance
    ports = [5005, 5006, 5007]  # Example ports for 3 instances

    # Shared state dictionary
    manager = Manager()
    shared_state = manager.dict()
    shared_state['submitted_transactions'] = manager.dict()
    shared_state['unconfirmed_transactions'] = manager.dict()

    # Start a process for each Flask app instance
    processes = []
    for port in ports:
        process = Process(target=run_app, args=(port, blockchain_address, shared_state))
        process.start()
        processes.append(process)

    # Join all processes
    for process in processes:
        process.join()

if __name__ == '__main__':
    freeze_support()
    main()
