#!/bin/bash

# Update the package list
sudo apt-get update

# Install Python and Pip
sudo apt-get install -y openssh-server
sudo apt-get install -y python3
sudo apt-get install -y python3-pip

# Install Flask and PyYAML libraries
pip3 install Flask PyYAML uuid blake3 requests cryptography numpy jsonify base58