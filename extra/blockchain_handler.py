from flask import Flask, request, jsonify
from blockchain_core import Blockchain, Transaction
from multiprocessing import Process
import yaml

def create_app(port, difficulty):
    app = Flask(__name__)

    
    blockchain = Blockchain(difficulty=difficulty)

    @app.route('/get_difficulty', methods=['GET'])
    def get_difficulty():
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

    return app

def run_instance(port, difficulty):
    app = create_app(port, difficulty)
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    
    configurations = [
        {'port': 5001, 'difficulty': 20},
        {'port': 5004, 'difficulty': 20},
        {'port': 5002, 'difficulty': 20},
        {'port': 5003, 'difficulty': 20},
    ]

    
    processes = []
    for config in configurations:
        process = Process(target=run_instance, args=(config['port'], config['difficulty']))
        process.start()
        processes.append(process)

    
    for process in processes:
        process.join()
