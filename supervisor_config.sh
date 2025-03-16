#!/bin/bash

# Installera Supervisor om det inte redan är installerat
sudo apt-get update
sudo apt-get install -y supervisor

# Skapa konfigurationsfilen för BörsRadar API
sudo bash -c 'cat > /etc/supervisor/conf.d/borsradar_api.conf << EOL
[program:borsradar_api]
command=/home/ubuntu/BorsRadar/venv/bin/uvicorn app.api:app --host 0.0.0.0 --port 8000
directory=/home/ubuntu/BorsRadar
user=ubuntu
autostart=true
autorestart=true
stderr_logfile=/home/ubuntu/BorsRadar/logs/api_error.log
stdout_logfile=/home/ubuntu/BorsRadar/logs/api_output.log
EOL'

# Skapa konfigurationsfilen för BörsRadar Scheduler
sudo bash -c 'cat > /etc/supervisor/conf.d/borsradar_scheduler.conf << EOL
[program:borsradar_scheduler]
command=/home/ubuntu/BorsRadar/venv/bin/python scheduler.py
directory=/home/ubuntu/BorsRadar
user=ubuntu
autostart=true
autorestart=true
stderr_logfile=/home/ubuntu/BorsRadar/logs/scheduler_error.log
stdout_logfile=/home/ubuntu/BorsRadar/logs/scheduler_output.log
EOL'

# Skapa logmapp om den inte redan finns
mkdir -p /home/ubuntu/BorsRadar/logs

# Ladda om supervisor-konfigurationen och starta tjänsterna
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status