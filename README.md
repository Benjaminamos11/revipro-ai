# Revipro AI - Steuerprüfungs-Assistent

🇨🇭 **100% Swiss Made** | AI-gestützte Steuerprüfung für Schweizer Gemeinden

## 🎯 Features

- ✅ **Automatische Dokumentenerkennung** (JA, SR, NAST, FiBu, Jahresrechnungen)
- ✅ **Intelligente Abstimmung** (Steuerabrechnungen vs. Finanzbuchhaltung)
- ✅ **AI-Chat-Assistent** (Opus 4.5 & Sonnet 4.5)
- ✅ **Dynamic Learning** (Lernt client-spezifische Muster)
- ✅ **Session-Management** (Alle Prüfungen in Sidebar)
- ✅ **Supabase-Integration** (Persistente Speicherung)

---

## 🚀 Quick Start (Lokal)

### 1. Backend starten
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Frontend starten
```bash
cd frontend
npm install
npm run dev -- -p 3001
```

### 3. Browser öffnen
```
http://localhost:3001
```

**Login-Passwort:** `revipro2026`

---

## 📦 Deployment auf Fly.io

Siehe: [DEPLOYMENT.md](./DEPLOYMENT.md)

**Quick Deploy:**
```bash
./deploy.sh
```

---

## 🗄️ Supabase Setup

**Projekt:** https://poeulzxkjcxeszfcsiks.supabase.co

**Tabellen:**
- `sessions` - Prüfungs-Sessions
- `documents` - PDF-Metadaten
- `chat_messages` - Chat-Verlauf
- `audit_results` - Prüfungsergebnisse
- `client_knowledge` - Gelerntes Wissen
- `learning_suggestions` - Lern-Vorschläge

**Storage:**
- Bucket `documents` - PDFs

---

## 🧠 AI-Modelle

| Modell | Use Case | Geschwindigkeit | Genauigkeit |
|--------|----------|-----------------|-------------|
| **Opus 4.5** | Kritische Analysen | Langsam | Sehr hoch |
| **Sonnet 4.5** | Routine-Fragen | Schnell | Hoch |

**Standard:** Opus 4.5

---

## 🔐 Umgebungsvariablen

### Backend
```bash
ANTHROPIC_API_KEY=sk-ant-api03-...
SUPABASE_URL=https://poeulzxkjcxeszfcsiks.supabase.co
SUPABASE_KEY=your_service_role_key
```

### Frontend
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 📊 Unterstützte Dokumente

### Steuerabrechnungen
- **JA** (Jahresabrechnung) - Aktuelles Jahr
- **SR** (Steuerrestanzen) - Vorjahre
- **NAST** (Nachsteuern)

### FiBu-Dokumente
- Kontoauszüge (1012.00, 2002.00)
- Kombinierte Dokumente (mehrere Konten)

### Jahresrechnungen
- Erfolgsrechnung (ER) - Konto 9100.xx
- Bilanz - Konten 1012.xx, 2002.xx, 2006.10

---

## 🎓 Learning System

Das System lernt automatisch:
- Spalten-Präferenzen ("Politische Gemeinde")
- Typische Konten pro Client
- Wiederkehrende Anomalien
- Dokumentformate

**Manuell speichern:**
```
User: "Merke dir: Spalte Politische Gemeinde verwenden"
AI: ✓ Gespeichert! Spalte 'Politische Gemeinde' für [Client]
```

---

## 🛠️ Tech Stack

- **Backend:** Python 3.9, FastAPI, pdfplumber
- **Frontend:** Next.js 14, React, Tailwind CSS, Framer Motion
- **AI:** Claude Opus 4.5 / Sonnet 4.5 (Anthropic)
- **Database:** Supabase (PostgreSQL)
- **Storage:** Supabase Storage
- **Deployment:** Fly.io

---

## 📝 Projekt-Log

Siehe: [PROJEKT_LOG.md](./PROJEKT_LOG.md)

---

## 📧 Support

- **Email:** contact@revipro.ch
- **Website:** https://revipro.ch

---

*© 2026 Revipro AG • 100% Swiss Made*
