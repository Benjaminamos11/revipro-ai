# Revipro Reconciliation Engine - Projekt-Log

## Projektübersicht
- **Projekt:** Automatisierte Steuerprüfung für Schweizer Gemeinden
- **Kunde:** Gemeinden (Pilotprojekt: Lufingen, Fehraltorf)
- **Stack:** Python/FastAPI (Backend), Next.js/React (Frontend), Claude Sonnet 4 (KI)

---

## 📅 17. Januar 2025

### Session-Zusammenfassung
Aufbau der Revipro Reconciliation Engine für die automatisierte Vorprüfung von Gemeindesteuern.

---

### 🎯 Hauptziele definiert

1. **Steuerabrechungen (GemoWinNG) parsen:**
   - JA (Jahresabschluss) - aktuelles Jahr
   - SR (Steuerrestanzen) - Vorjahre
   - NAST (Nachsteuern)

2. **FiBu-Kontoauszüge parsen:**
   - Konto 1012.00 (Steuerforderungen)
   - Konto 2002.00 (Steuerverpflichtungen)
   - Konto 2006.10 (GGST-Depots) - vorerst ausgeblendet

3. **Automatischer Abgleich:**
   - R805: Summe positive Restanzen = FiBu 1012.00
   - R806: Summe negative Restanzen = FiBu 2002.00

---

### 📝 Wichtige Erkenntnisse vom Kunden

**Logik der Verbuchung:**
- Positive Restanzen → Konto 1012.00 (Aktiven/Forderungen)
- Negative Restanzen → Konto 2002.00 (Passiven/Verpflichtungen)
- Minuszeichen entfällt auf Passivseite

**Zeilen-Mapping:**
| Dokument-Typ | Zeile | Wert | Buchungsart |
|--------------|-------|------|-------------|
| JA (aktuelles Jahr) | 45 "Total Restanzen" | SOLL | → 1012 oder 2002 |
| SR (Vorjahre) | 45 "Total Restanzenvortrag" | HABEN | Auflösung Vorjahr |
| SR (Vorjahre) | 51 "Total Restanzen" | SOLL | Neue Buchung |
| NAST | 44 "Total Restanzen Nachsteuern" | SOLL | → 1012 oder 2002 |

**Spalte:** Immer "Politische Gemeinde Lufingen" (oder entsprechende Körperschaft)

---

### 🔧 Technische Implementierungen

#### Version 1.0 - 3.0: Basis-Setup
- FastAPI Backend mit PDF-Parsing (pdfplumber)
- Next.js Frontend mit modernem Apple/iOS Design
- Orange-Gradient Farbschema, Glassmorphism
- Deutsche UI-Texte

#### Version 4.0: Lufingen-spezifische Logik
- Dokumenttyp-Erkennung (JA/SR/NAST/FiBu)
- Tabellenbasierte Extraktion mit Spalten-Mapping
- Negative-Wert-Erkennung aus Dateinamen ("Minusbetrag")
- Verbesserte FiBu-Saldo-Extraktion

#### Version 5.0: Claude AI Integration
- Anthropic SDK integriert
- Claude Sonnet 4 für intelligente Analyse
- KI-Insights: Feststellungen, Empfehlungen, Konfidenz
- Hybrid-Ansatz: Regex + LLM-Fallback

---

### 🐛 Gelöste Probleme

| Problem | Ursache | Lösung |
|---------|---------|--------|
| Frontend ohne CSS | Tailwind-Config falsch | Font-Variable korrigiert |
| Analyse hängt | Blocking I/O | ThreadPoolExecutor + asyncio |
| Hydration-Fehler | Theme-Toggle SSR | mounted-State hinzugefügt |
| FiBu als NAST erkannt | Falsche Priorität | FiBu-Erkennung zuerst |
| Falscher Saldo | Haben statt Saldo | Letzte Spalte nehmen |
| Negative nicht erkannt | Kein Minuszeichen | Dateiname-Hint |

---

### 📋 Offene Punkte / Nächste Schritte

- [ ] GGST (Konto 2006.10) - vorerst ausgeblendet wegen uneinheitlicher Formate
- [ ] Deployment (Vercel + Railway empfohlen)
- [ ] Mehrere Körperschaften (Sekundarschule, Kirche, etc.)
- [ ] Erfolgsrechnung (ER 9100) - nur bei Jahresabschluss verfügbar
- [ ] PDF-Upload mit Fortschrittsanzeige verbessern

---

### 💡 Architektur-Entscheidungen

**Warum Claude Sonnet 4?**
- Beste Balance: Genauigkeit vs. Kosten
- Exzellent für Tabellen/Zahlen-Extraktion
- Weniger "Halluzinationen" als Gemini bei Buchhaltung
- Kosten: ~CHF 0.05-0.20 pro Analyse

**Warum Hybrid-Ansatz?**
- Regex ist schnell und kostenlos für bekannte Formate
- LLM als Fallback für unbekannte/komplexe Dokumente
- LLM für finale Analyse und Erklärungen

---

### 📁 Projekt-Struktur

```
Revipro-ai/
├── backend/
│   ├── main.py          # FastAPI + Claude Integration
│   ├── requirements.txt  # Python Dependencies
│   └── venv/             # Virtual Environment
├── frontend/
│   ├── app/
│   │   ├── page.tsx      # Hauptseite
│   │   ├── layout.tsx    # Layout
│   │   └── globals.css   # Styling
│   └── package.json
├── PROJEKT_LOG.md        # Dieses Log
└── README.md
```

---

### 🔑 Konfiguration

**API-Key:** Anthropic Claude (in backend/main.py gespeichert)
**Ports:** Frontend: 3001, Backend: 8000

---

## Notizen für zukünftige Sessions

- Gemeinde Fehraltorf hat anderes Format als Lufingen
- Bei Vorprüfung ist Jahresrechnung noch nicht verfügbar
- Steuerperioden können über mehrere Jahre laufen
- CHF 2'025 von Lufingen ist ins falsche Jahr gerutscht (Periodenabgrenzung)

---

### 🆕 Passwort-Schutz & Supabase Security (Session 18.01.2026 - Security Update)

#### Passwort-Schutz (Prototype)
- Neue `/login` Seite mit Revipro Logo
- Hardcoded Passwort: `revipro2026`
- SessionStorage-basierte Auth
- Redirect zu Login wenn nicht authentifiziert

#### Supabase RLS aktiviert
- ✅ Row Level Security auf allen Tabellen
- ✅ Policies für alle Operations (Prototype-Mode)
- ✅ Storage Bucket "documents" gesichert
- ✅ Service Role Key wird vom Backend verwendet

**Behobene Security-Warnungen:**
- RLS auf `sessions`, `documents`, `chat_messages`, `audit_results`
- RLS auf `client_knowledge`, `learning_suggestions`
- Storage-Policy für Backend-Uploads

#### Revipro Logo integriert
- Login-Seite: Grosses Logo (128px)
- Chat-Header: Kleines Logo (32px)
- URL: https://revipro.ch/wp-content/uploads/2021/02/logo-1-e1613854437795.png

---

### 🆕 Model-Auswahl: Opus 4.5 vs Sonnet 4.5 (Session 18.01.2026 - Final)

#### Toggle-Switch im UI
- **Opus 4.5** (Standard) - Höchste Genauigkeit für Finanz-Dokumente
- **Sonnet 4.5** (Alternative) - Schneller, kostengünstiger

**Position:** Unter dem Chat-Input
**Design:** Toggle mit Orange-Gradient für aktive Auswahl

**Unterschiede:**
| Modell | Tokens | Geschwindigkeit | Genauigkeit | Use Case |
|--------|--------|-----------------|-------------|----------|
| **Opus 4.5** | 2000 | Langsam | Sehr hoch | Komplexe Prüfungen, kritische Differenzen |
| **Sonnet 4.5** | 1500 | Schnell | Hoch | Routine-Prüfungen, einfache Fragen |

**Empfehlung:** 
- Opus für erste Analyse und kritische Prüfungen
- Sonnet für Follow-up Fragen und schnelle Checks

**UI-Text entfernt:**
- ❌ "Powered by Claude Sonnet 4"
- ✅ "100% Swiss Made • Revipro AG"

---

### 🆕 Dynamic Learning System (Session 18.01.2026 - Finale)

#### Client-Specific Knowledge Base
Jede Gemeinde/Kirche/Schule bekommt ein **eigenes Wissensprofil**:

**Datenbank-Tabellen:**
- `client_knowledge` - Gespeicherte Erkenntnisse pro Client
- `learning_suggestions` - Vorschläge zur Benutzerbestätigung

**Was gelernt wird:**
- ✅ Spalten-Präferenzen ("Politische Gemeinde" ist Spalte 5)
- ✅ Typische Konten (immer 1012.00, 2002.00, 9100.xx)
- ✅ Wiederkehrende Anomalien (z.B. immer CHF 50 Verzugszinsen)
- ✅ Dokumentformate (GemoWinNG v3.2)
- ✅ Benutzerdefinierte Regeln

**Learning Flow:**
1. Nach Analyse: System erkennt Muster
2. Modal erscheint: "Neue Erkenntnisse entdeckt"
3. Benutzer akzeptiert oder lehnt ab
4. Bei Akzeptanz: Wissen wird in Supabase gespeichert
5. Nächste Prüfung: Claude hat dieses Wissen im Kontext

**Beispiel:**
```
🎓 Neue Erkenntnisse für Gemeinde Lufingen

📊 Typische Konten
Die Konten 1012.00, 2002.00 werden regelmässig
verwendet. Soll ich dies speichern?

[Speichern] [Ignorieren]
```

#### Proaktives Speichern durch Benutzer
Der Benutzer kann **direkt im Chat** Wissen speichern:

**Beispiele:**
- 👤 "Merke dir: Bei Lufingen ist Spalte Politische Gemeinde relevant"
  - 🤖 "✓ Gespeichert! Spalte 'Politische Gemeinde' für Gemeinde Lufingen."

- 👤 "Speichere: CHF 50.00 Differenz ist normal, das sind Verzugszinsen"
  - 🤖 "✓ Gespeichert! CHF 50 Differenz = Verzugszinsen als bekanntes Muster."

- 👤 "Die Kirche nutzt nur Konto 1012.10, nicht 1012.00"
  - 🤖 "✓ Gespeichert! Konto 1012.10 für diese Kirche."

**Automatische Erkennung:**
- System erkennt Keywords: "Merke dir", "Speichere", "Lerne", "Für nächstes Mal"
- Extrahiert relevante Informationen (Spalten, Konten, Beträge)
- Speichert in `client_knowledge` Tabelle
- Claude bestätigt das Gelernte

**Neue Quick-Actions:**
- "Merke dir: Spalte 'Politische Gemeinde' verwenden" (orange highlighted)
- "Speichere: CHF 50.00 Differenz ist normal"

#### Vorteile:
- Agent wird mit jeder Prüfung intelligenter
- Weniger Rückfragen bei wiederkehrenden Kunden
- Automatische Anpassung an Client-spezifische Besonderheiten
- Wissen bleibt erhalten über Sessions hinweg
- **Benutzer hat volle Kontrolle über gelerntes Wissen**

---

### 🆕 Auto-Naming & Editierbare Sessions (Session 18.01.2026 - Update)

#### Auto-Naming von Sessions
- Sessions werden **automatisch benannt** basierend auf Dokumenten
- Erkennt: "Gemeinde Lufingen", "Gemeinde Niederhasli", "Kirche", etc.
- Fallback: "Steuerprüfung" wenn nicht erkennbar

#### Editierbare Session-Namen
- **Klick auf Name** → Inline-Editing
- **Auto-Save** beim Verlassen (onBlur)
- **Enter** zum Speichern, **Escape** zum Abbrechen
- Synchronisiert mit Supabase

#### Welcome Message
- Erscheint **immer** wenn keine Messages vorhanden
- Zeigt Upload-Anleitung
- Dokumenttypen-Übersicht

#### Neue Backend-Endpoints:
- `PATCH /sessions/{id}/rename` - Session umbenennen

---

### 🆕 Sidebar mit Session-Management (Session 18.01.2026 - Spät)

#### Neue Sidebar (wie ChatGPT)
- **Collapsed by default** - nur 64px breit
- **Expand on Hover** - öffnet sich auf 280px
- **Icon-only Mode** - zeigt FileText-Icons wenn collapsed
- **Full Details Mode** - zeigt Datum, Titel, Dokument-Count wenn expanded
- **"Neue Prüfung" Button** - Plus-Icon (collapsed) oder mit Text (expanded)
- **Löschen-Funktion** - Trash-Icon bei Hover (nur expanded)
- **Smooth Animation** - 0.2s Übergang mit framer-motion

#### Neue Backend-Endpoints:
- `GET /sessions` - Liste aller Sessions aus Supabase
- `POST /sessions/new` - Neue Session erstellen
- `DELETE /sessions/{id}` - Session löschen (mit Cascade)

#### Features:
- Sessions werden automatisch geladen
- Aktive Session wird hervorgehoben
- Datum-Formatierung ("Heute", "Gestern", "vor X Tagen")
- Dokument-Count pro Session
- Mobile-responsiv (Hamburger-Menü)

---

### 🆕 Supabase-Integration & Animationen (Session 18.01.2026 - Nacht)

#### Supabase Datenbank
- Projekt: `poeulzxkjcxeszfcsiks` (eu-central-2)
- URL: https://poeulzxkjcxeszfcsiks.supabase.co

#### Tabellen:
- `sessions` - Audit-Sessions mit Org-Typ und Spalten-Präferenz
- `documents` - PDF-Metadaten und extrahierte Daten
- `chat_messages` - Konversations-Historie
- `audit_results` - Prüfungsergebnisse

#### Storage:
- Bucket: `documents` - PDFs werden persistent gespeichert
- Ermöglicht erneute Analyse mit neuem Kontext

#### Progress-Animation:
- Animierter Progress-Bar während der Analyse
- Verschiedene Stadien: "PDFs werden gelesen..." → "Daten werden extrahiert..." → "Prüfung wird durchgeführt..."
- Smooth 0-100% Animation mit framer-motion

---

### 🆕 Chat-First Redesign (Session 18.01.2026)

#### Komplett neues UI: Chat von Anfang an
- Die ganze App ist jetzt ein Chat
- Upload erscheint als erstes im Chat
- Ergebnisse werden inline im Chat angezeigt
- Natürlicherer Workflow

#### Reprocess-Funktion
- AI kann "nochmals analysieren" mit neuen Parametern
- Dateien werden im Backend gespeichert
- `/reprocess` Endpoint für erneute Analyse
- Benutzer kann Kontext geben (z.B. "Spalte Politische Gemeinde")

#### Saubere AI-Antworten
- Keine `###` Markdown-Headers mehr
- Natürlicher Fliesstext
- Kurze, prägnante Antworten
- Chat-Stil statt Dokument-Stil

#### Schnellaktionen
- "Weitere Dokumente hochladen"
- "Spalte 'Politische Gemeinde' verwenden"
- "Das ist ein Kirchen-Dokument"
- "Nochmals analysieren"

---

### 🆕 Neue Features (Session 17.01.2026 - Nacht)

#### Claude mit vollständigem Steuer-Fachwissen
Claude kennt jetzt:
- JA (Jahresabrechnung) vs SR (Steuerrestanzen) vs NAST (Nachsteuern)
- Kontenlogik: 1012.00 (Aktiven/Forderungen) vs 2002.00 (Passiven/Verpflichtungen)
- Spaltenlogik: Gemeinde vs Kirche vs Schule
- Typische Differenz-Ursachen
- Abstimmungslogik für Endsaldo-Prüfung

#### Inline Chat unter Ergebnissen
- Chat erscheint **direkt unter den Prüfungsergebnissen**
- Schnellfragen für häufige Anwendungsfälle
- Benutzer kann sofort Fragen stellen oder Kontext geben
- Claude kann Rückfragen stellen

#### Neue Schnellfragen:
- "Erkläre mir die Differenzen"
- "Fehlen noch Dokumente?"
- "Wie soll ich die Abweichung korrigieren?"
- "Das ist ein Kirchen-Dokument, nicht Gemeinde"

#### Quellensteuer (QVO) wird ignoriert
- Dokumente mit "Quellensteuer" oder "QVO" werden automatisch übersprungen
- Diese sind für Restanzen-Prüfung nicht relevant

#### Verbessertes Endsaldo-Parsing
- Korrigierte Logik für kombinierte FiBu-Dokumente
- Liest jetzt korrekt den Endsaldo (nicht Startsaldo)
- Erkennt aufgelöste Konten (Saldo = 0)

---

### 🆕 Neue Features (Session 17.01.2025 - Abend)

#### Chat-Kontext-Feld
- Benutzer kann zusätzlichen Kontext eingeben
- Z.B. "Das Dokument enthält beide Konten 1012.00 und 2002.00"
- Wird an Claude für besseres Verständnis übergeben

#### Kombinierte FiBu-Dokumente
- Neuer Dokumenttyp: `fibu_combined`
- Erkennt Dokumente mit mehreren Konten (1012.00 + 2002.00)
- Extrahiert Endsaldo für jedes Konto separat
- Beispiel: "Konti Restanzen Verpflichtungen 2024.pdf" (Niederhasli)

#### Erkannte Muster:
- "Fibukontoblatt" im Text → fibu_combined
- "Forderungen allgemeine Gemeindesteuern" → Konto 1012.00
- "Verpflichtungen aus allgemeinen Gemeindesteuern" → Konto 2002.00

---

### 📋 Neue Gemeinde: Niederhasli

Dokumentformat unterscheidet sich von Lufingen:
- Kombinierte Kontoauszüge (1012 + 2002 in einem PDF)
- Format: "Fibukontoblatt Standard"
- Spalten: Datum | Belegart | Belegnr. | Buchungsbeschreibung | ... | Soll | Haben | Saldo

---

---

## 🚀 Deployment-Vorbereitung (18.01.2026)

### Fly.io Setup
- **Backend App:** `revipro-backend` (Amsterdam Region)
- **Frontend App:** `revipro-frontend` (Amsterdam Region)
- Dockerfiles erstellt (Python 3.9 + Node 18)
- fly.toml Konfigurationen erstellt

### Deployment-Dateien:
- `backend/Dockerfile` - Python/FastAPI Container
- `frontend/Dockerfile` - Next.js Standalone Build
- `backend/fly.toml` - Fly Config (Port 8000)
- `frontend/fly.toml` - Fly Config (Port 3000)
- `deploy.sh` - Interaktives Deployment-Script
- `DEPLOYMENT.md` - Vollständige Anleitung
- `.gitignore` - Git-Ignore für Python/Node/Fly

### Environment Variables:
- Backend: `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`
- Frontend: `NEXT_PUBLIC_API_URL`

### CORS aktualisiert:
- Fly.io URLs hinzugefügt
- Wildcard für `*.fly.dev`

### Login-Schutz:
- Neue `/login` Seite
- Hardcoded Passwort: `revipro2026`
- SessionStorage-Auth
- Revipro Logo integriert

---

---

## 📊 Detailliertes Activity-Logging (18.01.2026 - Analytics)

### Comprehensive Logging System
Jede User-Aktion wird in Supabase geloggt für:
- **Debugging** (Was ist schief gelaufen?)
- **Performance-Analyse** (Wo sind Bottlenecks?)
- **Feature-Usage** (Was nutzen User am meisten?)
- **Learning-Improvement** (Welche Patterns erkennen?)

### Neue Supabase-Tabellen:
- `activity_logs` - Alle Events mit Timing und Kontext
- `user_sessions` - Login-Tracking und Session-Dauer
- `error_logs` - Detaillierte Fehler mit Stack-Traces

### Was wird geloggt:
| Event | Daten |
|-------|-------|
| Login (Erfolg/Fehler) | Timestamp, User-Agent |
| Dokumente Upload | File-Count, Names, Größe |
| Analyse Start/End | Dauer, Resultate, Matches/Mismatches |
| Chat-Messages | Länge, Modell, Response-Zeit |
| AI-Responses | Modell, Dauer, Wissen gespeichert? |
| Fehler | Type, Message, Stack-Trace |

### Analytics-Endpoint:
`GET /analytics` - Zusammenfassung der letzten 7 Tage

### Views für schnelle Queries:
- `analytics_summary` - Events gruppiert nach Typ/Kategorie
- `common_errors` - Häufigste Fehler

### Dokumentation:
- `ANALYTICS_GUIDE.md` - SQL-Queries für Analytics
- Privacy-konform (keine sensiblen Daten)

---

*Zuletzt aktualisiert: 18. Januar 2026, 03:30*
