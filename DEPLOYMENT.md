# Revipro Deployment Guide

## 🚀 Deployment auf Fly.io

### Voraussetzungen

1. **Fly.io CLI installieren:**
```bash
brew install flyctl
# oder
curl -L https://fly.io/install.sh | sh
```

2. **Anmelden:**
```bash
fly auth login
```

---

## 📦 Backend Deployment

### 1. App erstellen
```bash
cd backend
fly launch --no-deploy
# App Name: revipro-backend
# Region: ams (Amsterdam - closest to Switzerland)
```

### 2. Secrets setzen
```bash
fly secrets set ANTHROPIC_API_KEY=<your_anthropic_key>

fly secrets set SUPABASE_URL=https://poeulzxkjcxeszfcsiks.supabase.co

fly secrets set SUPABASE_KEY=<your_supabase_service_role_key>
```

**✅ Service Role Key:** Bereits konfiguriert!

### 3. Deployen
```bash
fly deploy
```

### 4. Logs prüfen
```bash
fly logs
```

---

## 🎨 Frontend Deployment

### 1. Backend-URL aktualisieren
Öffne `frontend/app/page.tsx` und ersetze alle `http://localhost:8000` durch die Fly.io Backend-URL.

Oder nutze Environment Variable:
```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
```

### 2. App erstellen
```bash
cd frontend
fly launch --no-deploy
# App Name: revipro-frontend
# Region: ams (Amsterdam)
```

### 3. Secrets setzen
```bash
fly secrets set NEXT_PUBLIC_API_URL=https://revipro-backend.fly.dev
```

### 4. Deployen
```bash
fly deploy
```

### 5. Logs prüfen
```bash
fly logs
```

---

## 🔧 Nützliche Befehle

### Status prüfen
```bash
fly status
```

### SSH in Container
```bash
fly ssh console
```

### App neu starten
```bash
fly apps restart revipro-backend
fly apps restart revipro-frontend
```

### Skalierung
```bash
# Backend skalieren
fly scale count 2 -a revipro-backend

# VM-Größe ändern
fly scale vm shared-cpu-1x -a revipro-backend
```

---

## 🌐 URLs nach Deployment

- **Backend API:** https://revipro-backend.fly.dev
- **Frontend:** https://revipro-frontend.fly.dev

---

## 🔐 Supabase Service Role Key holen

1. Gehe zu: https://supabase.com/dashboard/project/poeulzxkjcxeszfcsiks/settings/api
2. Kopiere den **service_role** Key (nicht den anon key!)
3. Setze ihn als Secret: `fly secrets set SUPABASE_KEY=...`

---

## 📝 Checklist vor Deployment

- [ ] Alle Secrets gesetzt (ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_KEY)
- [ ] Backend-URL im Frontend aktualisiert
- [ ] CORS im Backend auf Fly.io URLs erweitert
- [ ] Supabase RLS Policies aktiviert ✅
- [ ] .gitignore erstellt ✅
- [ ] Docker-Images bauen lokal: `docker build -t test .`

---

## 🔄 Updates deployen

```bash
# Backend Update
cd backend
fly deploy

# Frontend Update
cd frontend
fly deploy
```

---

## 🐛 Troubleshooting

### Backend startet nicht
```bash
fly logs -a revipro-backend
# Prüfe auf fehlende Secrets oder Import-Fehler
```

### Frontend zeigt 500 Error
```bash
fly logs -a revipro-frontend
# Prüfe ob NEXT_PUBLIC_API_URL gesetzt ist
```

### Supabase Connection Error
- Prüfe ob Service Role Key korrekt ist
- Prüfe ob RLS Policies aktiviert sind
- Prüfe Network in Fly.io Dashboard

---

## 💰 Kosten (Schätzung)

- **Backend:** ~$5-10/Monat (shared-cpu-1x)
- **Frontend:** ~$5-10/Monat (shared-cpu-1x)
- **Supabase:** Free Tier ausreichend für Prototype
- **Total:** ~$10-20/Monat

---

*Erstellt: 18.01.2026*
