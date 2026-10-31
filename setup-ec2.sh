#!/usr/bin/env bash
# setup-ec2.sh — Quick setup script to run directly on an AWS EC2 Ubuntu instance
set -euo pipefail

echo "===> [1/4] Setting up 4 GB Swapfile (essential for 1 GB RAM Free Tier)..."
if [ ! -f /swapfile ]; then
  sudo fallocate -l 4G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  sudo sysctl vm.swappiness=10
  echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
  echo "Swap configured successfully."
else
  echo "Swapfile already exists, skipping."
fi

echo "===> [2/4] Installing Docker and Docker Compose..."
sudo apt-get update -qq
sudo apt-get install -y -qq ca-certificates curl gnupg git python3-cryptography
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update -qq
sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"

echo "===> [3/4] Preparing Project & Environment..."
if [ ! -d "$HOME/cpd-etl" ]; then
  git clone https://github.com/jainashish03/cpd-etl.git "$HOME/cpd-etl"
fi
cd "$HOME/cpd-etl"

if [ ! -f .env ]; then
  cp .env.example .env
  # Generate unique Airflow Fernet Key
  FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  sed -i "s|^AIRFLOW_FERNET_KEY=.*|AIRFLOW_FERNET_KEY=${FERNET_KEY}|" .env
  echo "Created .env with generated AIRFLOW_FERNET_KEY."
fi

echo "===> [4/4] Starting Docker Compose containers..."
sudo docker compose up -d --build

echo ""
echo "============================================================"
echo "  CPD ETL Pipeline & Metabase are now running on AWS!"
echo "  - Airflow:   http://$(curl -s ifconfig.me):8080"
echo "  - Metabase:  http://$(curl -s ifconfig.me):3000"
echo "============================================================"

