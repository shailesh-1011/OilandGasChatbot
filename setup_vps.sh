#!/bin/bash
# ============================================
# Oil & Gas Chatbot - VPS Setup Script
# Run this on your VPS: bash /root/oilgaschatbot/setup_vps.sh
# ============================================

set -e  # Exit on error

echo "============================================"
echo "  Oil & Gas Chatbot - VPS Setup"
echo "============================================"

# Step 1: Update system
echo ""
echo "[1/7] Updating system packages..."
apt update && apt upgrade -y

# Step 2: Install Python and dependencies
echo ""
echo "[2/7] Installing Python and tools..."
apt install -y python3 python3-pip python3-venv nginx

# Step 3: Setup virtual environment
echo ""
echo "[3/7] Creating Python virtual environment..."
cd /root/oilgaschatbot
python3 -m venv venv
source venv/bin/activate

# Step 4: Install Python packages
echo ""
echo "[4/7] Installing Python packages (this may take a few minutes)..."
pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Step 5: Create systemd service
echo ""
echo "[5/7] Setting up systemd service..."
cat > /etc/systemd/system/oilgas-api.service << 'EOF'
[Unit]
Description=Oil & Gas Chatbot API
After=network.target

[Service]
User=root
WorkingDirectory=/root/oilgaschatbot
Environment="PATH=/root/oilgaschatbot/venv/bin"
ExecStart=/root/oilgaschatbot/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 --timeout 120 web.app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable oilgas-api
systemctl start oilgas-api

# Step 6: Configure Nginx
echo ""
echo "[6/7] Configuring Nginx..."
cat > /etc/nginx/sites-available/oilgas << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_connect_timeout 120s;
    }
}
EOF

# Enable site
ln -sf /etc/nginx/sites-available/oilgas /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# Step 7: Setup daily scraper cron job
echo ""
echo "[7/7] Setting up daily scraper cron job..."
(crontab -l 2>/dev/null | grep -v "oilgaschatbot"; echo "0 6 * * * cd /root/oilgaschatbot && /root/oilgaschatbot/venv/bin/python scheduler.py >> /var/log/oilgas-scraper.log 2>&1") | crontab -

# Open firewall ports
echo ""
echo "Opening firewall ports..."
ufw allow 80/tcp 2>/dev/null || true
ufw allow 443/tcp 2>/dev/null || true
ufw allow 5000/tcp 2>/dev/null || true

# Done!
echo ""
echo "============================================"
echo "  ✅ SETUP COMPLETE!"
echo "============================================"
echo ""
echo "Your API is now running at:"
echo "  http://202.61.254.26"
echo "  http://202.61.254.26:5000"
echo ""
echo "API Endpoints:"
echo "  POST http://202.61.254.26/api/search"
echo "  GET  http://202.61.254.26/api/health"
echo "  GET  http://202.61.254.26/api/stats"
echo ""
echo "Useful commands:"
echo "  Check status:  systemctl status oilgas-api"
echo "  View logs:     journalctl -u oilgas-api -f"
echo "  Restart:       systemctl restart oilgas-api"
echo ""
