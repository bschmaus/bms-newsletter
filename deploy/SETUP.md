# BMS Newsletter — Google VM Setup

## 1. VM erstellen (Google Cloud Console)

- Maschinentyp: `e2-small` reicht (2 vCPU, 2 GB RAM)
- OS: Debian 12 oder Ubuntu 22.04 LTS
- Firewall: HTTP-Traffic erlauben (Port 80) und Port 8000 freigeben

### GCP Firewall-Regel für Port 8000

```bash
gcloud compute firewall-rules create bms-newsletter \
  --allow tcp:8000 \
  --source-ranges 0.0.0.0/0 \
  --description "BMS Newsletter Web UI"
```

---

## 2. Server einrichten

SSH auf die VM, dann:

```bash
# System updaten
sudo apt update && sudo apt upgrade -y

# Python + git
sudo apt install -y python3 python3-pip python3-venv git

# User anlegen
sudo useradd -m -s /bin/bash bms
sudo su - bms
```

---

## 3. App deployen

```bash
# Als user 'bms'
cd /opt  # oder /home/bms
git clone https://github.com/DEIN-REPO/bms-newsletter.git
cd bms-newsletter

# Virtualenv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Data-Verzeichnis initialisieren
python3 -c "from config import ensure_data_dir; ensure_data_dir()"

# Persistente Datendateien kopieren (vom MacBook via scp):
# scp data/voice.md bms@VM-IP:/opt/bms-newsletter/data/
# scp data/school_context.md bms@VM-IP:/opt/bms-newsletter/data/
# scp data/corporate_design.md bms@VM-IP:/opt/bms-newsletter/data/
# scp data/learnings.md bms@VM-IP:/opt/bms-newsletter/data/
# scp data/topics_archive.md bms@VM-IP:/opt/bms-newsletter/data/
```

---

## 4. .env anlegen

```bash
nano /opt/bms-newsletter/.env
```

Inhalt:
```
ANTHROPIC_API_KEY=sk-ant-DEIN-KEY
WEB_USER=bms
WEB_PASS=sicheres-passwort-hier

# Optional: SMTP für Content Collector
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=deine@email.de
SMTP_PASSWORD=app-passwort
SMTP_FROM=deine@email.de
NOTIFY_EMAIL=empfaenger@schule.de
```

Berechtigungen sichern:
```bash
chmod 600 /opt/bms-newsletter/.env
```

---

## 5. systemd Service installieren

```bash
# Als root
sudo cp /opt/bms-newsletter/deploy/bms-newsletter.service \
        /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable bms-newsletter
sudo systemctl start bms-newsletter

# Status prüfen
sudo systemctl status bms-newsletter
sudo journalctl -u bms-newsletter -f
```

---

## 6. Testen

```bash
# Lokal auf der VM
curl http://localhost:8000/

# Vom MacBook (VM-IP z.B. 34.90.123.45)
open http://34.90.123.45:8000
```

Login: Benutzername und Passwort aus `WEB_USER` / `WEB_PASS` in `.env`.

---

## 7. Updates deployen

```bash
sudo su - bms
cd /opt/bms-newsletter
git pull
source venv/bin/activate
pip install -r requirements.txt  # nur wenn requirements geändert
sudo systemctl restart bms-newsletter
```

---

## 8. Content Collector automatisieren (Cron)

```bash
# Als user 'bms'
crontab -e

# Alle 14 Tage um 8:00 Uhr
0 8 */14 * * cd /opt/bms-newsletter && venv/bin/python3 collector.py >> /tmp/bms-collector.log 2>&1
```

---

## 9. Optional: nginx als Reverse Proxy (für späteres TLS)

```bash
sudo apt install -y nginx

sudo nano /etc/nginx/sites-available/bms-newsletter
```

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_buffering    off;
        proxy_cache        off;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        proxy_http_version 1.1;
        proxy_set_header   Connection "";
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/bms-newsletter /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx
```

Dann Port 8000 in der GCP Firewall wieder schließen (nur Port 80 offen lassen).
