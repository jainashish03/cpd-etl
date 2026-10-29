#!/usr/bin/env bash
# deploy-gce.sh — Create a Google Cloud VM and deploy cpd-etl with Docker Compose
#
# Prerequisites:
#   1. Install gcloud CLI: https://cloud.google.com/sdk/docs/install
#   2. Run:  gcloud auth login
#   3. Run:  gcloud config set project YOUR_PROJECT_ID
#
# Usage:
#   chmod +x deploy-gce.sh
#   ./deploy-gce.sh          # creates VM, opens firewall, deploys stack
#   ./deploy-gce.sh teardown  # deletes everything

set -euo pipefail

# ── Configuration (edit these) ───────────────────────────────────────────────
VM_NAME="cpd-etl"
ZONE="asia-south1-a"           # Mumbai — closest to you; change if needed
MACHINE_TYPE="e2-small"        # 2 vCPU, 2 GB RAM (~$13/month); bump to e2-medium if slow
DISK_SIZE="20GB"
FIREWALL_RULE="allow-cpd-etl"
# ─────────────────────────────────────────────────────────────────────────────

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'

PROJECT=$(gcloud config get-value project 2>/dev/null)
if [[ -z "$PROJECT" ]]; then
  echo -e "${RED}Error: No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID${NC}"
  exit 1
fi

teardown() {
  echo -e "${CYAN}Deleting VM ${VM_NAME}...${NC}"
  gcloud compute instances delete "$VM_NAME" --zone="$ZONE" --quiet || true
  echo -e "${CYAN}Deleting firewall rule ${FIREWALL_RULE}...${NC}"
  gcloud compute firewall-rules delete "$FIREWALL_RULE" --quiet || true
  echo -e "${GREEN}Done. All resources removed.${NC}"
}

if [[ "${1:-}" == "teardown" ]]; then
  teardown
  exit 0
fi

echo -e "${CYAN}[1/4] Creating VM: ${VM_NAME} (${MACHINE_TYPE}) in ${ZONE}...${NC}"
gcloud compute instances create "$VM_NAME" \
  --zone="$ZONE" \
  --machine-type="$MACHINE_TYPE" \
  --boot-disk-size="$DISK_SIZE" \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --tags=cpd-etl-server \
  --metadata=startup-script='#!/bin/bash
    apt-get update -qq
    apt-get install -y -qq docker.io docker-compose-plugin git
    systemctl enable docker && systemctl start docker
    usermod -aG docker $(logname 2>/dev/null || echo ubuntu)
  '

echo -e "${CYAN}[2/4] Opening firewall for ports 8080 (Airflow) and 3000 (Metabase)...${NC}"
gcloud compute firewall-rules create "$FIREWALL_RULE" \
  --allow=tcp:8080,tcp:3000 \
  --target-tags=cpd-etl-server \
  --description="Allow Airflow and Metabase for cpd-etl" \
  2>/dev/null || echo "Firewall rule already exists, skipping."

echo -e "${CYAN}[3/4] Waiting for VM startup script to finish (~60s)...${NC}"
sleep 60

echo -e "${CYAN}[4/4] Deploying cpd-etl on the VM...${NC}"
gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="
  set -e
  cd /home/\$(whoami)
  git clone https://github.com/jainashish03/cpd-etl.git || (cd cpd-etl && git pull)
  cd cpd-etl
  cp .env.example .env
  # Generate a real Fernet key
  FERNET_KEY=\$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())' 2>/dev/null || echo 'CHANGE_ME')
  sed -i \"s|^AIRFLOW_FERNET_KEY=.*|AIRFLOW_FERNET_KEY=\${FERNET_KEY}|\" .env
  sudo docker compose up -d --build
  echo '--- Containers ---'
  sudo docker compose ps
"

EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" \
  --zone="$ZONE" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Deployed! Access from any device:${NC}"
echo -e ""
echo -e "  Airflow:   ${CYAN}http://${EXTERNAL_IP}:8080${NC}"
echo -e "  Metabase:  ${CYAN}http://${EXTERNAL_IP}:3000${NC}"
echo -e ""
echo -e "  SSH:       gcloud compute ssh ${VM_NAME} --zone=${ZONE}"
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
