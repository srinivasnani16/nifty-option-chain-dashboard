#!/bin/bash
# ============================================================
# NIFTY OPTION CHAIN — AUTO START SCRIPT
# Starts both the data collector and dashboard on boot
# ============================================================

cd /home/ubuntu
source /home/ubuntu/nifty_env/bin/activate

# Start data collector in background screen session
screen -dmS nifty bash -c "source /home/ubuntu/nifty_env/bin/activate && python3 /home/ubuntu/option_chain.py >> /home/ubuntu/logs/collector.log 2>&1"

# Wait 5 seconds then start dashboard
sleep 5
screen -dmS dashboard bash -c "source /home/ubuntu/nifty_env/bin/activate && python3 /home/ubuntu/dashboard.py >> /home/ubuntu/logs/dashboard.log 2>&1"

echo "Both services started at $(date)" >> /home/ubuntu/logs/startup.log
