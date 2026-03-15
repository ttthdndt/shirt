#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy.sh — Deploy Shirt Pipeline on Contabo (CyberPanel / Ubuntu)
# Run as root: bash deploy.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e  # exit on any error

APP_DIR="/var/www/shirt_pipeline"
APP_USER="www-data"
PORT=5050
DOMAIN=""   # leave empty = use server IP

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[x]${NC} $1"; exit 1; }

[[ $EUID -ne 0 ]] && err "Run as root: sudo bash deploy.sh"

# ── 1. System packages ────────────────────────────────────────────────────────
log "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git unzip openssl

# ── 2. App directory ──────────────────────────────────────────────────────────
log "Setting up app directory at $APP_DIR..."
mkdir -p "$APP_DIR"
mkdir -p "$APP_DIR/ssl"

# If shirt_app.zip is in current dir, extract it
if [ -f "shirt_app.zip" ]; then
    log "Extracting shirt_app.zip..."
    unzip -o shirt_app.zip -d /tmp/shirt_extract
    # Handle nested folder (shirt_app/shirt_app/ or shirt_app/)
    if [ -d "/tmp/shirt_extract/shirt_app" ]; then
        cp -r /tmp/shirt_extract/shirt_app/. "$APP_DIR/"
    else
        cp -r /tmp/shirt_extract/. "$APP_DIR/"
    fi
    rm -rf /tmp/shirt_extract
else
    warn "shirt_app.zip not found in current directory."
    warn "Please manually copy your app files to $APP_DIR and re-run."
fi

# ── 3. Python virtual environment ─────────────────────────────────────────────
log "Creating Python virtual environment..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
"$APP_DIR/venv/bin/pip" install --quiet gunicorn

# ── 4. .env file ──────────────────────────────────────────────────────────────
if [ ! -f "$APP_DIR/.env" ]; then
    log "Creating .env file..."
    cat > "$APP_DIR/.env" << 'ENVEOF'
GROK_API_KEY=xai-ApoeBxVHEbedVEC8U1wI0j4Kyq842XRyxCFposhTe9DisPG1JwvqIrtay6qiWrhhdJq2rVb8EDHqvkjZ
WP_BASE_URL=https://motasport.com
WP_USERNAME=admin
WP_APP_PASS=O0kK pqnZ 6GCx SoJN 4Ru0 YLKh
SECRET_KEY=CHANGE_THIS_TO_A_RANDOM_STRING_BEFORE_DEPLOYING
ENVEOF
    warn ".env created — edit it at $APP_DIR/.env if needed."
else
    log ".env already exists, skipping."
fi

# ── 5. Self-signed SSL certificate ───────────────────────────────────────────
log "Generating self-signed SSL certificate..."
SERVER_IP=$(hostname -I | awk '{print $1}')
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout "$APP_DIR/ssl/selfsigned.key" \
    -out    "$APP_DIR/ssl/selfsigned.crt" \
    -subj "/C=US/ST=State/L=City/O=MotaSport/CN=$SERVER_IP" \
    -addext "subjectAltName=IP:$SERVER_IP" \
    2>/dev/null
chmod 600 "$APP_DIR/ssl/selfsigned.key"
log "SSL cert created for IP: $SERVER_IP"

# ── 6. Gunicorn config ────────────────────────────────────────────────────────
log "Writing gunicorn config..."
cat > "$APP_DIR/gunicorn.conf.py" << GEOF
bind = "0.0.0.0:$PORT"
workers = 2
worker_class = "sync"
timeout = 300          # 5 min — Grok image gen can take 60s per prompt
keepalive = 5
loglevel = "info"
accesslog = "/var/log/shirt_pipeline/access.log"
errorlog  = "/var/log/shirt_pipeline/error.log"

# SSL — Flask served directly over HTTPS
keyfile  = "$APP_DIR/ssl/selfsigned.key"
certfile = "$APP_DIR/ssl/selfsigned.crt"
GEOF

# ── 7. Log directory ──────────────────────────────────────────────────────────
mkdir -p /var/log/shirt_pipeline
chown "$APP_USER" /var/log/shirt_pipeline

# ── 8. Permissions ────────────────────────────────────────────────────────────
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
chmod -R 755 "$APP_DIR"
mkdir -p /tmp/uploads /tmp/outputs /tmp/garments
chown "$APP_USER" /tmp/uploads /tmp/outputs /tmp/garments

# ── 9. Systemd service ────────────────────────────────────────────────────────
log "Creating systemd service..."
cat > /etc/systemd/system/shirt_pipeline.service << SEOF
[Unit]
Description=Shirt Pattern Pipeline (Flask + Gunicorn)
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/gunicorn app:app -c $APP_DIR/gunicorn.conf.py
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SEOF

# ── 10. Open firewall port ────────────────────────────────────────────────────
log "Opening port $PORT in firewall..."
if command -v ufw &>/dev/null; then
    ufw allow $PORT/tcp comment "Shirt Pipeline" 2>/dev/null || true
fi
# CyberPanel uses CSF sometimes
if command -v csf &>/dev/null; then
    csf -a "$(hostname -I | awk '{print $1}')" 2>/dev/null || true
    warn "CSF detected — you may need to add port $PORT in CyberPanel → Security → CSF Firewall → Allow incoming."
fi

# ── 11. Start service ─────────────────────────────────────────────────────────
log "Starting shirt_pipeline service..."
systemctl daemon-reload
systemctl enable shirt_pipeline
systemctl restart shirt_pipeline
sleep 2

# ── 12. Done ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Deployment complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  App URL:   ${YELLOW}https://$SERVER_IP:$PORT${NC}"
echo -e "  Status:    ${YELLOW}systemctl status shirt_pipeline${NC}"
echo -e "  Logs:      ${YELLOW}journalctl -u shirt_pipeline -f${NC}"
echo -e "  App logs:  ${YELLOW}tail -f /var/log/shirt_pipeline/error.log${NC}"
echo -e "  Restart:   ${YELLOW}systemctl restart shirt_pipeline${NC}"
echo ""
echo -e "  NOTE: Browser will show a security warning (self-signed cert)."
echo -e "  Click 'Advanced → Proceed' to continue — this is expected."
echo ""

if systemctl is-active --quiet shirt_pipeline; then
    echo -e "${GREEN}  Service is RUNNING ✅${NC}"
else
    echo -e "${RED}  Service FAILED to start. Check logs:${NC}"
    echo -e "  journalctl -u shirt_pipeline -n 50 --no-pager"
fi
