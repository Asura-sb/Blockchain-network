import threading
from flask import jsonify

class MiningPool:
    def __init__(self, flask_port, shared_state):
        self.flask_port = flask_port
        self.shared_state = shared_state
        self.lock = threading.Lock()

    def add_transaction(self, transaction):
        with self.lock:
            tx_id = transaction['tx_id']
            self.shared_state['submitted_transactions'][tx_id] = transaction

    def confirm_transactions(self, transactions_data):
        with self.lock:
            for tx_data in transactions_data:
                tx_id = tx_data['tx_id']
                if tx_id in self.shared_state['unconfirmed_transactions']:
                    del self.shared_state['unconfirmed_transactions'][tx_id]
    
    def get_transaction_counts(self):
        with self.lock:
            return {
                "submitted_count": len(self.shared_state['submitted_transactions']),
                "unconfirmed_count": len(self.shared_state['unconfirmed_transactions'])
            }

    def get_transactions(self):
        with self.lock:
            transactions = list(self.shared_state['submitted_transactions'].values())[:10]
            for tx in transactions:
                tx_id = tx['tx_id']
                self.shared_state['unconfirmed_transactions'][tx_id] = tx
                del self.shared_state['submitted_transactions'][tx_id]
            return transactions

    def list_transactions(self, public_key):
        with self.lock:
            all_transactions = list(self.shared_state['submitted_transactions'].values()) + \
                               list(self.shared_state['unconfirmed_transactions'].values())
            filtered_transactions = [txn for txn in all_transactions if txn.get('sender') == public_key]
        return filtered_transactions

    def transaction_status(self, tx_id):
        with self.lock:
            if tx_id in self.shared_state['submitted_transactions']:
                return "submitted"
            elif tx_id in self.shared_state['unconfirmed_transactions']:
                return "unconfirmed"
            else:
                return "unknown"
