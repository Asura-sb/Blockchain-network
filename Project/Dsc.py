# dsc.py
import argparse
import yaml

from Wallet1 import Wallet1
from Blockchain import Blockchain
from Pool import MiningPool
from Metronome import Metronome
from Validator1 import Validator1
from Monitor import Monitor
from flask import Flask, request

app = Flask(__name__)

def load_config():
    try:
        with open('config.yaml', 'r') as config_file:
            config = yaml.safe_load(config_file)
        return config
    except FileNotFoundError:
        print("Config file not found.")
        return None

def main():
    config = load_config()

    if config is not None:
        parser = argparse.ArgumentParser(description="DSC: DataSys Coin Blockchain v1.0")
        parser.add_argument("command", help="Supported commands: wallet, blockchain, pool, metronome, validator, monitor, help")
        args = parser.parse_args()

        if args.command == "help":
            print_help()
        elif args.command == "wallet":
            Wallet1(config['wallet1']).run()
        elif args.command == "blockchain":
            Blockchain(config['blockchain']).run()
        elif args.command == "pool":
            mining_pool = MiningPool(config['pool'])
            mining_pool.start_pool()
        elif args.command == "metronome":
            metronome = Metronome(config['metronome'])
            app.run
        elif args.command == "validator":
            validator = Validator1(config['validator'])
            app.run
        elif args.command == "monitor":
            monitor = Monitor(config['monitor'])
            app.run
        else:
            print("Invalid command. Use './dsc help' for supported commands.")

def print_help():
    print("DSC: DataSys Coin Blockchain v1.0")
    print("Help menu, supported commands:")
    print("./dsc help")
    print("./dsc wallet")
    print("./dsc blockchain")
    print("./dsc pool")
    print("./dsc metronome")
    print("./dsc validator")
    print("./dsc monitor")
    pass

if __name__ == "__main__":
    main()
