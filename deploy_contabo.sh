#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy_contabo.sh  —  Deploy shirt-pipeline on a Contabo VPS (Ubuntu 22/24)
#
# Usage:
#   1. SSH into your VPS
#   2. Upload this repo to /var/www/shirt-pipeline  (or git clone it)
#   3. chmod +x deploy_contabo.sh && sudo ./deploy_contabo.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

APP_DIR="/var/www/shirt-pipeline"
APP_USER="www-data"
DOMAIN=""          # <- set your domain or IP, e.g. "pipeline.motasport.com"
PORT="5000"

echo "=== 1. System packages ==="
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx

echo "=== 2. Python environment ==="
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "=== 3. Persistent folders ==="
mkdir -p /var/shirt-pipeline/{uploads,outputs,garments}
chown -R "$APP_USER":"$APP_USER" /var/shirt-pipeline

echo "=== 4. .env file ==="
if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  echo ""
  echo "⚠  Edit $APP_DIR/.env and fill in your real values, then re-run."
  echo "   Required: GROK_API_KEY, WP_APP_PASS, SECRET_KEY"
  exit 1
fi

echo "=== 5. systemd service ==="
cat > /etc/systemd/system/shirt-pipeline.service << EOF
[Unit]
Description=Shirt Pattern Pipeline (Flask + Gunicorn)
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
Environment="UPLOAD_FOLDER=/var/shirt-pipeline/uploads"
Environment="OUTPUT_FOLDER=/var/shirt-pipeline/outputs"
Environment="GARMENT_FOLDER=/var/shirt-pipeline/garments"
ExecStart=$APP_DIR/venv/bin/gunicorn \
    --workers 2 \
    --threads 4 \
    --timeout 300 \
    --bind 127.0.0.1:$PORT \
    --access-logfile /var/log/shirt-pipeline-access.log \
    --error-logfile  /var/log/shirt-pipeline-error.log \
    app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable shirt-pipeline
systemctl restart shirt-pipeline
echo "Service started."

echo "=== 6. Nginx config ==="
cat > /etc/nginx/sites-available/shirt-pipeline << EOF
server {
    listen 80;
    server_name ${DOMAIN:-_};

    client_max_body_size 20M;

    location / {
        proxy_pass         http://127.0.0.1:$PORT;
        proxy_read_timeout 300s;    # allow Grok's 30-60s + upload time
        proxy_send_timeout 300s;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_buffering    off;     # stream logs to browser in real time
    }
}
EOF

ln -sf /etc/nginx/sites-available/shirt-pipeline /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

echo ""
echo "=== Done! ==="
echo "App running at: http://${DOMAIN:-YOUR_SERVER_IP}"
echo ""
if [ -n "$DOMAIN" ]; then
  echo "To add HTTPS:"
  echo "  certbot --nginx -d $DOMAIN"
fi
echo ""
echo "Useful commands:"
echo "  sudo systemctl status shirt-pipeline    # check service"
echo "  sudo journalctl -u shirt-pipeline -f    # live logs"
echo "  sudo systemctl restart shirt-pipeline   # restart after code changes"
echo "  sudo tail -f /var/log/shirt-pipeline-error.log"
