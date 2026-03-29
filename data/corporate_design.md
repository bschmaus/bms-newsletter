# Corporate Design — BMS Newsletter

## Identität
- **Schulname (lang):** Bilinguale Montessori Schule Ingelheim
- **Schulname (kurz):** BMS
- **Adresse:** Carolinenstraße 2, 55218 Ingelheim am Rhein
- **Website:** https://bilinguale-montessori-schule.de
- **BMS News-URL:** https://bilinguale-montessori-schule.de/de/aktuelles/news-de
- **BMS Termine-URL:** https://bilinguale-montessori-schule.de/de/aktuelles/termine

## Logo
- **URL:** http://bilinguale-montessori-schule.de/images/Logo_BMS.png
- **Verwendung:** Zentriert, oben im Header, max. 160px breit
- **Alt-Text:** Bilinguale Montessori Schule Ingelheim
- **Linkziel:** https://bilinguale-montessori-schule.de

## Farbpalette
| Name | Hex | Verwendung |
|---|---|---|
| BMS Dunkelblau | #2B5B84 | Primärfarbe: Überschriften, Links, Footer-Hintergrund, Zitat-Rand, Akzente |
| BMS Mittelblau | #3A7CA5 | Sekundärfarbe: Section-Labels, Datumsspalte Termine |
| Body-Hintergrund | #f5f5f0 | Äußerer Email-Hintergrund (warmes Hellgrau) |
| Content-Hintergrund | #ffffff | Haupt-Inhaltsbereich |
| Zitat-Hintergrund | #f0f4f8 | Hintergrund Pull-Quote-Boxen |
| Trennlinie | #e8ecf0 | Horizontale Sektions-Trennlinien |
| Termine-Box | #f8f4e8 | Hintergrund Termin-Box (warmes Creme) |
| Termine-Rand | #e0d8c4 | Rahmen Termin-Box |
| Termine-Trennlinie | #ede5cc | Zeilentrennlinien in Terminliste |
| Termine-Datum | #3A7CA5 | Datumsangaben in Terminbox |
| Text | #333333 | Fließtext |
| Sekundärtext | #666666 | Quellenangaben, Hinweistexte |
| Footer-Text hell | #ccdce8 | Fließtext im Footer |
| Link-Farbe | #2B5B84 | Alle Hyperlinks |
| Frei-Badge HG | #d4e8d0 | Hintergrund "unterrichtsfrei"-Badge |
| Frei-Badge Text | #2a6b24 | Text "unterrichtsfrei"-Badge |
| Termin-Hinweis | #8B6914 | Hervorgehobene Terminhinweise (z.B. Anmeldung erforderlich) |
| Artikel-Separator | #d0dce8 | Gestrichelte Trennlinie zwischen Artikeln |

## Typografie
- **Fließtext:** Arial, Helvetica, sans-serif — 15px, #333333, line-height 1.7
- **Absatz-Abstand:** margin-bottom: 10px
- **Überschriften (Artikel):** Arial, Helvetica, sans-serif — 17px, bold, #2B5B84, line-height 1.35
- **Section-Labels:** Arial, Helvetica, sans-serif — 11px, bold, uppercase, letter-spacing 0.14em, #3A7CA5
- **Zitate (kursiv):** font-style: italic, #2B5B84
- **Links:** color:#2B5B84, text-decoration:none
- **Footer:** Arial, Helvetica, sans-serif — 12px, line-height 1.7
- **Keine Web-Fonts** (Outlook-Kompatibilität, nur System-Fonts)

## HTML-Email — Technische Pflichtregeln (Outlook)
Der Newsletter wird als HTML direkt in Outlook eingefügt (copy-paste in die Compose-Ansicht).
Outlook Desktop 2007–2021 rendert E-Mails über die Word-Engine. Daher gelten:

### Was PFLICHT ist
- **Alle Styles als inline `style="..."`** direkt auf jedem HTML-Element
- **Table-basiertes Layout** für alle strukturellen Bereiche (`<table>`, `<tr>`, `<td>`)
- **Breite über `width`-Attribut** auf `<table>` (nicht per CSS `max-width`)
- **Äußere Tabelle:** `<table width="100%" bgcolor="#f5f5f0" cellpadding="0" cellspacing="0">`
- **Innere Content-Tabelle:** `<table width="640" align="center" bgcolor="#ffffff" cellpadding="0" cellspacing="0">`
- **Farben:** nur Hex-Werte (#rrggbb) als `bgcolor`-Attribut UND als inline-style `background-color`
- **Zellen-Padding:** über `cellpadding`-Attribut oder inline `style="padding:..."`

### Was VERBOTEN ist (Outlook ignoriert es)
- `<style>`-Block im `<head>` — wird komplett ignoriert
- CSS-Klassen via `class="..."` (nur inline-Styles funktionieren)
- `box-shadow`
- `border-radius`
- `overflow: hidden`
- `max-width` auf block-Elementen
- `display: flex`, `display: grid`, `display: inline-block`
- `rgba()`, `rgb()` — nur Hex
- `:hover`, `:focus`, `::before`, `::after` Pseudo-Selektoren
- `@media` Queries
- `<div>` als Layout-Container

## Newsletter-Struktur (Aufbau, Reihenfolge)
1. **Logo** — zentriert, 160px breit, verlinkt auf BMS-Website
2. **Header-Zeile** mit "News aus der BMS · Newsletter" in Mittelblau, Trennlinie unten
3. **Eröffnungszitat** — Maria-Montessori-Zitat aus dem Newsletter-Text, Pull-Quote-Stil: blauer linker Rand (#2B5B84, 5px), Hintergrund #f0f4f8, kursiv, zentriert, mit Quellenangabe
4. **Begrüßung** — "Liebe Schulgemeinschaft," fett blau + Einleitungstext
5. **Sektionen** (je mit Section-Label, Trennlinie davor):
   - News aus der BMS
   - Aus der Montessori-Welt
   - Bildungspolitik — was bedeutet das für uns?
6. **Termine-Box** — cremefarbener Hintergrund (#f8f4e8), Datum-Spalte links (130px, blau, bold), Event-Spalte rechts
7. **Abschluss-Zitat** — echtes Montessori-Zitat (Pull-Quote-Stil, blauer linker Rand)
8. **Footer** — Hintergrund #2B5B84, weiß, Schulname + Adresse + Website

## Abschluss-Zitat — Pflichtregeln
- MUSS ein **echtes, verifizierbares Maria-Montessori-Zitat** sein (kein Satz aus dem Newsletter)
- Thematisch zum roten Faden der Ausgabe passend
- Format: kursiver Zitattext + Quellenangabe (Werk, Erscheinungsjahr)
- Bekannte Quellen: *Kinder sind anders* (1936), *The Absorbent Mind* (1949, dt. *Das kreative Kind*), *Grundlagen meiner Pädagogik* (1934)

## Links
- BMS-Website: immer `https://bilinguale-montessori-schule.de` (nie `bms-ingelheim.de`)
- "Zum Artikel"-Links → `https://bilinguale-montessori-schule.de/de/aktuelles/news-de`
- Alle Links: `style="color:#2B5B84; text-decoration:none;"`
