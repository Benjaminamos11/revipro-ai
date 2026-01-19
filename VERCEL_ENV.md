# 🚀 Vercel Deployment - Environment Variables

## Frontend auf Vercel deployen

### 1. Vercel Projekt erstellen

```bash
cd frontend
vercel
```

Oder via Vercel Dashboard:
1. Gehe zu https://vercel.com/new
2. Import Repository: `Benjaminamos11/revipro-ai`
3. Root Directory: `frontend`
4. Framework Preset: `Next.js`

---

## 2. Environment Variables setzen

### In Vercel Dashboard → Settings → Environment Variables:

| Name | Value | Environment |
|------|-------|-------------|
| `NEXT_PUBLIC_API_URL` | `https://revipro-backend.fly.dev` | Production, Preview, Development |

---

## 3. Vercel CLI (Alternative)

```bash
cd frontend

# Production
vercel env add NEXT_PUBLIC_API_URL production
# Wert: https://revipro-backend.fly.dev

# Preview
vercel env add NEXT_PUBLIC_API_URL preview
# Wert: https://revipro-backend.fly.dev

# Development
vercel env add NEXT_PUBLIC_API_URL development
# Wert: https://revipro-backend.fly.dev
```

---

## 4. Deployment starten

### Via CLI:
```bash
cd frontend
vercel --prod
```

### Via Dashboard:
- Push to GitHub → Vercel deployt automatisch

---

## 5. Domain-Konfiguration (Optional)

Nach Deployment können Sie eine Custom Domain hinzufügen:

1. Vercel Dashboard → Settings → Domains
2. Add Domain: z.B. `app.revipro.ch`
3. DNS-Einträge bei Ihrem Provider hinzufügen

---

## ✅ Nach Deployment

### URLs:
- **Backend:** https://revipro-backend.fly.dev ✅
- **Frontend:** https://revipro-ai-[hash].vercel.app (oder Custom Domain)

### Testen:
1. Frontend-URL öffnen
2. Login mit Passwort: `revipro2026`
3. Dokumente hochladen
4. Prüfen ob Backend verbunden ist

---

## 🔧 Troubleshooting

### Backend nicht erreichbar
```bash
# CORS prüfen
curl https://revipro-backend.fly.dev/
# Sollte: {"status":"ok",...} zurückgeben
```

### Environment Variable nicht gesetzt
```bash
# In Vercel Dashboard prüfen
# Settings → Environment Variables
# NEXT_PUBLIC_API_URL muss gesetzt sein
```

### Build-Fehler
```bash
# Vercel Deployment Logs prüfen
# Dashboard → Deployments → [Your Deployment] → Logs
```

---

## 📊 Vercel-spezifische Optimierungen

### `vercel.json` (Optional)
```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "devCommand": "npm run dev",
  "installCommand": "npm install",
  "regions": ["fra1"],
  "functions": {
    "app/**": {
      "maxDuration": 60
    }
  }
}
```

---

## 🌐 Final URLs

Nach erfolgreichem Deployment:

| Service | URL | Status |
|---------|-----|--------|
| **Backend API** | https://revipro-backend.fly.dev | ✅ LIVE |
| **Frontend** | https://your-project.vercel.app | ⏳ Deploying |

---

*Erstellt: 18.01.2026*
