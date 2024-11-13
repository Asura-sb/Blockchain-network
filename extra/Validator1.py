import yaml
import os
import requests
import threading
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from blake3 import blake3
import time
import numpy as np
import mmap
from flask import Flask, request, jsonify

app = Flask(__name__)

class PoW:
    def __init__(self, config):
        self.fingerprint = config["validator"]["keys"]["fingerprint"]
        self.public_key = config["validator"]["keys"]["fingerprint"]
        self.proof_config = config["validator"]["proof_pow"]
        self.threads = self.proof_config.get("threads", 2)

    def _hash_input(self, block_hash, difficulty, nonce):
        input_data = block_hash + str(difficulty) + str(nonce) + self.public_key
        return blake3(input_data.encode()).hexdigest()

    def find_nonce_threaded(self, block_hash, difficulty, start_nonce, end_nonce, result, stop_event):
        for nonce in range(start_nonce, end_nonce):
            if stop_event.is_set():
                return
            if self._hash_input(block_hash, difficulty, nonce).startswith('0' * difficulty):
                result.append(nonce)
                stop_event.set()
                return

    def perform_pow(self, block_hash, block_id, difficulty):
        print(f"{time.strftime('%Y%m%d %H:%M:%S.%f')} DSC v1.0")
        print(f"{time.strftime('%Y%m%d %H:%M:%S.%f')} Proof of Work ({self.threads} threads)")
        print(f"{time.strftime('%Y%m%d %H:%M:%S.%f')} Fingerprint: {self.fingerprint}")
        print(f"{time.strftime('%Y%m%d %H:%M:%S.%f')} block {block_id}, diff {difficulty}, hash {block_hash}")

        start_p_time = time.time()
        time_limit = 6  # 6 seconds time limit
        nonce_range = 2 ** 32 // self.threads
        result = []
        stop_event = threading.Event()

        while time.time() - start_p_time < time_limit and not result:
            threads = []
            for i in range(self.threads):
                start_nonce = i * nonce_range
                end_nonce = start_nonce + nonce_range
                thread = threading.Thread(target=self.find_nonce_threaded, args=(block_hash, difficulty, start_nonce, end_nonce, result, stop_event))
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join(timeout=max(0, start_p_time + time_limit - time.time()))

            if result or stop_event.is_set():
                break

        end_time = time.time()
        hash_rate = self.calculate_hash_rate(start_p_time, end_time)

        if result:
            print(f"{time.strftime('%Y%m%d %H:%M:%S.%f')} block {block_id}, NONCE {result[0]} ({hash_rate} MH/s)")
            return True, result[0], hash_rate
        else:
            print(f"{time.strftime('%Y%m%d %H:%M:%S.%f')} block {block_id}, NONCE -1 ({hash_rate} MH/s)")
            return False, -1, hash_rate

    def calculate_hash_rate(self, start_time, end_time):
        elapsed_time = end_time - start_time
        hash_rate = (2**22) / (1024**2) / elapsed_time  # Hash rate in MH/s
        return round(hash_rate, 2)


class PoM:
    def __init__(self, config):
        self.fingerprint = config["validator"]["keys"]["fingerprint"]
        self.public_key = config["validator"]["keys"]["fingerprint"]
        self.proof_config = config["validator"]["proof_pom"]
        self.threads = self.proof_config.get("threads", 2)

    def _convert_memory_to_bytes(self, memory_string):
        units = {"K": 1024, "M": 1024**2, "G": 1024**3}
        unit = memory_string[-1]
        num = int(memory_string[:-1])
        return num * units.get(unit.upper(), 1)

    def _hash_input(self, nonce):
        input_data = self.fingerprint + self.public_key + str(nonce)
        return blake3(input_data.encode()).hexdigest()

    def generate_hashes_threaded(self, start_nonce, end_nonce, hashes, lock, stop_event):
        for nonce in range(start_nonce, end_nonce):
            if stop_event.is_set():
                return
            hash_output = self._hash_input(nonce)
            with lock:
                hashes.append((hash_output, nonce))


    def generate_and_organize_hashes(self, start_time, time_limit):
       
        num_hashes = self._convert_memory_to_bytes(self.proof_config['memory']) // 64
        hashes = []
        lock = threading.Lock()
        stop_event = threading.Event()
        threads = []

        for i in range(self.threads):
            start_nonce = i * num_hashes // self.threads
            end_nonce = start_nonce + num_hashes // self.threads
            thread = threading.Thread(target=self.generate_hashes_threaded, args=(start_nonce, end_nonce, hashes, lock, stop_event))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join(max(0, start_time + time_limit - time.time()))

        hashes.sort()
        return hashes

    def perform_pom(self, block_hash, block_id, difficulty):
        start_p_time = time.time()
        time_limit = 6
        print(f"{time.strftime('%Y%m%d %H:%M:%S.%f')} DSC v1.0")
        print(f"{time.strftime('%Y%m%d %H:%M:%S.%f')} Proof of Memory ({self.threads} threads)")
        print(f"{time.strftime('%Y%m%d %H:%M:%S.%f')} Fingerprint: {self.fingerprint}")
        print(f"{time.strftime('%Y%m%d %H:%M:%S.%f')} block {block_id}, diff {difficulty}, hash {block_hash}")

        nonce = -1  # Default value if not found
        hashes = self.generate_and_organize_hashes(start_p_time, time_limit)
        if hashes:
            
            nonce = self.timed_binary_search(hashes, block_hash[:difficulty], time_limit)

        end_time = time.time()
        hash_rate = self.calculate_hash_rate(start_p_time, end_time, len(hashes))

        if nonce != -1:
            print(f"{time.strftime('%Y%m%d %H:%M:%S.%f')} Block hash found, NONCE: {nonce}, Hash Rate: {hash_rate} H/s")
            return True, nonce, hash_rate
        else:
            print(f"{time.strftime('%Y%m%d %H:%M:%S.%f')} Block hash not found, NONCE: -1, Hash Rate: {hash_rate} H/s")
            return False, -1, hash_rate

    def timed_binary_search(self, hashes, prefix, time_limit):
        start_time = time.time()
        end_time = start_time + time_limit
        start_index = 0
        end_index = len(hashes) - 1

        while start_index <= end_index and time.time() < end_time:
            mid_index = (start_index + end_index) // 2
            mid_hash = hashes[mid_index][0] if isinstance(hashes[mid_index], (tuple, list)) else mid_hash

            if mid_hash.startswith(prefix):
                return hashes[mid_index][1]

            if mid_hash < prefix:
                start_index = mid_index + 1
            else:
                end_index = mid_index - 1

        return -1

    def calculate_hash_rate(self, start_time, end_time, total_hashes):
        elapsed_time = end_time - start_time
        return total_hashes / elapsed_time
    

class PoS:
    def __init__(self, config, validator_id):
        self.config = config
        self.validator_id = validator_id
        self.fingerprint = config["validator"]["keys"]["fingerprint"]
        self.public_key = config["validator"]["keys"]["fingerprint"]
        self.proof_config = config["validator"]["proof_pos"]
        self.vault_path = self.proof_config.get("vault", f"./default_vault_{self.validator_id}.yaml")
        self.buckets = self.proof_config["buckets"]
        self.cup_size = self.proof_config["cup_size"]
        self.cups_per_bucket = self.proof_config["cups_per_bucket"]
        self.check_and_generate_vault()

    def check_and_generate_vault(self):
        if not os.path.exists(self.vault_path):
            print(f"Vault file not found at {self.vault_path}. Generating new vault.")
            self.generate_to_file()
            self.config["validator"]["proof_pos"]["vault"] = self.vault_path
            self.save_config()

    def save_config(self):
        with open(self.config_path, 'w') as file:
            yaml.dump(self.config, file)

    def _hash_input(self, nonce):
        input_data = self.fingerprint + self.public_key + str(nonce)
        return blake3(input_data.encode()).hexdigest()

    def generate_to_file(self):
        
        total_hashes = self.buckets * self.cup_size * self.cups_per_bucket
        with open(self.vault_path, 'wb') as file:
            for i in range(total_hashes):
                hash_output = self._hash_input(i)
                prefix = int(hash_output[0:2], 16)
                data = f'{prefix:02x}:{hash_output}:{i}\n'
                file.write(data.encode())

    def calculate_hash_rate(self, start_time, end_time, total_hashes):
        elapsed_time = end_time - start_time
        hash_rate = total_hashes / elapsed_time
        return round(hash_rate, 2)

    def _perform_pos(self, latest_block_hash, current_difficulty):
        start_p_time = time.time()
        time_limit = 6
        print(f"{time.strftime('%Y%m%d %H:%M:%S.%f')} Performing Proof of Space Check")
        print(f"{time.strftime('%Y%m%d %H:%M:%S.%f')} DSC Validator v1.0 -- Proof of Space")

        nonce = -1  
        accesses = 0
        while time.time() - start_p_time < time_limit:
            nonce, accesses = self.lookup(latest_block_hash, current_difficulty)
            if nonce != -1:
                break  

        end_time = time.time()
        hash_rate = self.calculate_hash_rate(start_p_time, end_time, self.buckets * self.cup_size * self.cups_per_bucket)

        
        if nonce != -1:
            return True, nonce, hash_rate
        else:
            return False, -1, hash_rate

    def lookup(self, target_hash, difficulty):
        
        access_count = 0
        with open(self.vault_path, 'r+b') as f:
            mmapped_file = mmap.mmap(f.fileno(), 0)
            target_prefix = int(target_hash[0:2], 16)
            for line in iter(mmapped_file.readline, b""):
                access_count += 1
                prefix, hash_output, nonce = line.decode().strip().split(':')
                if int(prefix, 16) == target_prefix and hash_output.startswith(target_hash[:difficulty]):
                    mmapped_file.close()
                    return int(nonce), access_count
            mmapped_file.close()
        return -1, access_count

    


class Validator:
    def __init__(self, validator_id):
        self.validator_id = validator_id
        self.config_path = f'validator{validator_id}.yaml'  
        self.config = self.load_config(self.config_path)
        self.ensure_fingerprint_and_key()
        self.blockchain_server = self.config['blockchain']['server_address']
        self.metronome_server = self.config['metronome']['server_address']
        self.pow = PoW(self.config)
        self.pom = PoM(self.config)
        self.pos = PoS(self.config, self.validator_id)
        self.is_running = False
        


    
    

    def run(self):
        self.is_running = True
        while self.is_running:
            try:
                start_time = time.time()
                latest_block_hash, block_id = self.get_latest_block_info()
                if latest_block_hash:
                    print(f"Latest Block Hash: {latest_block_hash}")
                    difficulty = self.get_current_difficulty()
                    print(f"Current difficulty: {difficulty}, Block ID: {block_id}")
                    proof_result = self.perform_proof(latest_block_hash, block_id, difficulty)
                    if proof_result is not None:
                        proof_type, nonce, hash_rate = proof_result
                        print(f"Proof result obtained: {proof_type}, NONCE: {nonce}, Hash Rate: {hash_rate}")
                        self.notify_metronome_validator_win(proof_type, nonce, hash_rate)
                        print("Notified metronome validator win, proceeding to next block")
                    else:
                        print("Proof result is None, proceeding to next block")
                else:
                    print("No latest block hash available, retrying...")
                    time.sleep(1)  
                elapsed_time = time.time() - start_time
                if elapsed_time < 6:
                    time.sleep(6 - elapsed_time)
            except Exception as e:
                print(f"Error in run loop: {e}")
                break


    
    def load_config(self, config_path):
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)

    def ensure_fingerprint_and_key(self):
      validator_config = self.config.get('validator', {})
      keys_config = validator_config.get('keys', {})

      if 'fingerprint' not in keys_config or 'public_key' not in keys_config:
          
          private_key = rsa.generate_private_key(
              public_exponent=65537,
              key_size=2048,
              backend=default_backend()
          )

          
          public_key = private_key.public_key().public_bytes(
              encoding=serialization.Encoding.OpenSSH,
              format=serialization.PublicFormat.OpenSSH
          )
        
          
          fingerprint = blake3(public_key).hexdigest()

          
          self.config.setdefault('validator', {}).setdefault('keys', {})['fingerprint'] = fingerprint
          self.config.setdefault('validator', {}).setdefault('keys', {})['public_key'] = public_key.decode()

          
          self.save_config()

    def save_config(self):
        with open(self.config_path, 'w') as file:
            yaml.dump(self.config, file)


    def start(self):
        if not self.is_running:
            self.is_running = True
            print("Validator started.")
        else:
            print("Validator is already running.")

    def stop(self):
        if self.is_running:
            self.is_running = False
            print("Validator stopped.")
        else:
            print("Validator is not running.")
    
    
    
    def get_latest_block_info(self):
      response = requests.get(f"{self.blockchain_server}/get_latest_block_hash")
      if response.status_code == 200:
         data = response.json()
         return data["latest_block_hash"], data["block_id"]
      return None, None

    def get_current_difficulty(self):
        try:
            response = requests.get(f"{self.metronome_server}/get_current_difficulty")
            if response.status_code == 200:
                difficulty_data = response.json()
                return difficulty_data.get("difficulty")
            else:
                print("Failed to get current difficulty from Metronome, using default.")
                return self.config.get('difficulty', 30)  # Default difficulty if request fails
        except Exception as e:
            print(f"Error getting difficulty: {e}")
            return self.config.get('difficulty', 30)

    def perform_proof(self, latest_block_hash, block_id, difficulty):
        if difficulty is None:
            print("Difficulty is None, skipping proof.")
            return None
        
        proof_time_limit = 6  
        start_time = time.time()
        while time.time() - start_time < proof_time_limit:
            if self.config.get('validator', {}).get('proof_pow', {}).get('enable', False):
                proof_success, nonce, hash_rate = self.pow.perform_pow(latest_block_hash, block_id, difficulty)
                if proof_success:
                    return "pow", nonce, hash_rate
            elif self.config.get('validator', {}).get('proof_pom', {}).get('enable', False):
                proof_success, nonce, hash_rate = self.pom.perform_pom(latest_block_hash, block_id, difficulty)
                if proof_success:
                    return "pom", nonce, hash_rate
            elif self.config.get('validator', {}).get('proof_pos', {}).get('enable', False):
                self.pos.check_and_generate_vault()  # Generate vault only if it doesn't exist
                proof_success, nonce, hash_rate = self.pos._perform_pos(latest_block_hash, difficulty)
                if proof_success:
                    return "pos", nonce, hash_rate
                
            latest_block_hash, _ = self.get_latest_block_info()  

        return None

    def register_with_metronome(self):
        data = {
            "validator_id": self.validator_id,
            "fingerprint": self.config["validator"]['keys']["fingerprint"]
        }
        response = requests.post(f"{self.metronome_server}/register_validator", json=data)
     

    
    def notify_metronome_validator_win(self, proof_type, nonce, hash_rate):
      data = {
          "validator_id": self.validator_id,
          "proof_type": proof_type,
          "nonce": nonce,
          "hash_rate": hash_rate
        }
      
      response = requests.post(f"{self.metronome_server}/report_statistics", json=data)


@app.route('/validate_and_mine', methods=['POST'])
def validate_and_mine():
    latest_block_hash, block_id = validator.get_latest_block_info()
    difficulty = validator.get_current_difficulty()
    proof_result = validator.perform_proof(latest_block_hash, block_id, difficulty)
    if proof_result is not None:
        proof_type, nonce, hash_rate = proof_result
        validator.notify_metronome_validator_win(proof_type, nonce, hash_rate)
        return jsonify({"message": "Validation successful"})
    else:
        return jsonify({"error": "Proof failed"}), 400

# Main execution
if __name__ == "__main__":
    validator_id = 1  # Set this based on the specific validator instance
    validator = Validator(validator_id)
    validator.register_with_metronome()
    print("Validator Running")
    validator.start()
    try:
        validator.run()
    except KeyboardInterrupt:
        print("Stopping Validator")
        validator.stop()

    
    