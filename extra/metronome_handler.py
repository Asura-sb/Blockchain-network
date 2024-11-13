from flask import Flask, request, jsonify
import requests
from metronome_core import Metronome
from multiprocessing import Process
import yaml

def create_app(blockchain_server, pool_server):
    app = Flask(__name__)
    metronome = Metronome(blockchain_server, pool_server)

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

    

    return app

def run_app(port, blockchain_server, pool_server):
    app = create_app(blockchain_server, pool_server)
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    with open('config.yaml', "r") as file:
        config = yaml.safe_load(file)

    blockchain_server = config['blockchain']['server_address']
    pool_server = config['pool']['server_address']

    # Define ports for each instance
    ports = [5008, 5009, 5010]  # Example ports for 3 instances

    # Start a process for each Flask app instance
    processes = []
    for port in ports:
        process = Process(target=run_app, args=(port, blockchain_server, pool_server))
        process.start()
        processes.append(process)

    # Join all processes
    for process in processes:
        process.join()
