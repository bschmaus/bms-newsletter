# BMS Newsletter

Automatisierte Newsletter-Generierung für die Bilinguale Montessori Schule Ingelheim.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env  # API-Key eintragen
```

## Nutzung

```bash
python orchestrator.py              # Volle Pipeline
python orchestrator.py --from write  # Ab Newsletter Writer
python orchestrator.py --only scan   # Nur Scanning
```

## Pipeline

1. **Scanning** — BMS-Website + Montessori-Quellen scrapen
2. **Newsletter Writer** — Newsletter-Entwurf erstellen
3. **Red Team** — Qualitäts- & Tonalitätsprüfung
4. **Assessment** — Learnings für nächste Ausgabe

## Manueller Schritt

Newsletter-Entwurf aus `data/newsletter_archive.md` in Email kopieren und versenden.
