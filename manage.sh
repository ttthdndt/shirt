#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# manage.sh — Quick management commands for Shirt Pipeline
# Usage: bash manage.sh [command]
# ─────────────────────────────────────────────────────────────────────────────

APP_DIR="/var/www/shirt_pipeline"
SERVICE="shirt_pipeline"

case "$1" in
  start)
    systemctl start $SERVICE
    echo "Started."
    ;;
  stop)
    systemctl stop $SERVICE
    echo "Stopped."
    ;;
  restart)
    systemctl restart $SERVICE
    echo "Restarted."
    ;;
  status)
    systemctl status $SERVICE
    ;;
  logs)
    journalctl -u $SERVICE -f
    ;;
  update)
    echo "Pulling latest code and restarting..."
    if [ -f "shirt_app.zip" ]; then
      unzip -o shirt_app.zip -d /tmp/shirt_extract
      if [ -d "/tmp/shirt_extract/shirt_app" ]; then
        rsync -av --exclude='.env' --exclude='ssl/' /tmp/shirt_extract/shirt_app/. "$APP_DIR/"
      fi
      rm -rf /tmp/shirt_extract
      "$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
      chown -R www-data:www-data "$APP_DIR"
      systemctl restart $SERVICE
      echo "Updated and restarted."
    else
      echo "shirt_app.zip not found in current directory."
    fi
    ;;
  *)
    echo "Usage: bash manage.sh [start|stop|restart|status|logs|update]"
    ;;
esac
