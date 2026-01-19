# 📊 Revipro Analytics & Logging Guide

## 🎯 Was wird geloggt?

### Alle User-Aktivitäten werden in Supabase gespeichert:

| Event | Kategorie | Daten |
|-------|-----------|-------|
| **Login (Erfolg)** | auth | Timestamp, User-Agent |
| **Login (Fehlversuch)** | auth | Password-Length |
| **Neue Session** | system | Session-ID |
| **Dokumente hochgeladen** | ui | File-Count, Names, Size |
| **Analyse gestartet** | document | File-Count, Context |
| **Analyse abgeschlossen** | document | Results, Duration, Matches/Mismatches |
| **Chat-Message** | chat | Message-Length, Model |
| **AI-Response** | ai | Model, Response-Length, Duration |
| **Session gelöscht** | system | Session-ID |
| **Wissen gespeichert** | learning | Knowledge-Type, Client-Name |
| **Fehler** | error | Error-Type, Message, Stack-Trace |

---

## 📋 Supabase Tabellen

### 1. `activity_logs` (Haupt-Logging)
```sql
- session_id: Welche Prüfung
- event_type: Was ist passiert
- event_category: auth|document|chat|ai|ui|system
- data: Detaillierte Event-Daten (JSON)
- duration_ms: Wie lange hat es gedauert
- status: success|error|warning|info
- user_agent: Browser-Info
- timestamp: Wann
```

### 2. `user_sessions` (Login-Tracking)
```sql
- login_attempts: Anzahl Login-Versuche
- successful_login: Boolean
- session_duration_minutes: Wie lange war User aktiv
- total_documents_processed: Anzahl verarbeitete Dokumente
- total_chat_messages: Anzahl Chat-Nachrichten
```

### 3. `error_logs` (Fehler-Tracking)
```sql
- error_type: parsing_error|api_error|timeout|validation_error
- error_message: Fehler-Text
- stack_trace: Vollständiger Stack
- context: Zusätzliche Infos
- resolved: Boolean (für Nachverfolgung)
```

---

## 📊 Analytics Abfragen

### Analytics-Dashboard abrufen
```bash
curl http://localhost:8000/analytics
```

**Response:**
```json
{
  "summary": {
    "total_sessions": 15,
    "total_documents": 127,
    "total_activities": 543,
    "period_days": 7
  },
  "activity_by_type": [
    {"event_type": "chat_message_received", "event_count": 89},
    {"event_type": "analysis_complete", "event_count": 15},
    ...
  ],
  "common_errors": [
    {"error_type": "timeout", "occurrence_count": 3},
    ...
  ]
}
```

---

## 🔍 Nützliche SQL-Queries (Supabase Dashboard)

### 1. Heute's Aktivitäten
```sql
SELECT 
    event_type,
    COUNT(*) as count,
    AVG(duration_ms) as avg_duration
FROM activity_logs
WHERE timestamp > NOW() - INTERVAL '1 day'
GROUP BY event_type
ORDER BY count DESC;
```

### 2. User-Journey für eine Session
```sql
SELECT 
    timestamp,
    event_type,
    data,
    duration_ms,
    status
FROM activity_logs
WHERE session_id = 'your-session-id'
ORDER BY timestamp ASC;
```

### 3. Fehler-Rate
```sql
SELECT 
    DATE(timestamp) as date,
    COUNT(*) as total_events,
    COUNT(CASE WHEN status = 'error' THEN 1 END) as errors,
    ROUND(100.0 * COUNT(CASE WHEN status = 'error' THEN 1 END) / COUNT(*), 2) as error_rate
FROM activity_logs
GROUP BY DATE(timestamp)
ORDER BY date DESC;
```

### 4. Beliebteste Dokument-Typen
```sql
SELECT 
    data->>'file_names' as documents,
    COUNT(*) as uploads
FROM activity_logs
WHERE event_type = 'files_uploaded'
GROUP BY data->>'file_names'
ORDER BY uploads DESC
LIMIT 10;
```

### 5. Durchschnittliche Analyse-Dauer
```sql
SELECT 
    AVG(duration_ms) / 1000 as avg_seconds,
    MIN(duration_ms) / 1000 as min_seconds,
    MAX(duration_ms) / 1000 as max_seconds
FROM activity_logs
WHERE event_type = 'analysis_complete';
```

### 6. Chat-Statistiken
```sql
SELECT 
    data->>'model' as model_used,
    COUNT(*) as messages,
    AVG(duration_ms) as avg_response_time_ms
FROM activity_logs
WHERE event_type = 'chat_response_sent'
GROUP BY data->>'model';
```

### 7. Learning-System Adoption
```sql
SELECT 
    COUNT(*) as total_suggestions,
    COUNT(CASE WHEN status = 'accepted' THEN 1 END) as accepted,
    COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected,
    ROUND(100.0 * COUNT(CASE WHEN status = 'accepted' THEN 1 END) / COUNT(*), 2) as acceptance_rate
FROM learning_suggestions;
```

---

## 🚨 Error-Monitoring

### Ungelöste Fehler anzeigen
```sql
SELECT 
    error_type,
    error_message,
    timestamp,
    session_id
FROM error_logs
WHERE resolved = false
ORDER BY timestamp DESC;
```

### Fehler als gelöst markieren
```sql
UPDATE error_logs
SET resolved = true, resolution_notes = 'Fixed in version X'
WHERE id = 'error-id';
```

---

## 📈 Analytics-Dashboard (Planned)

**Zukünftiges Feature:** Visuelles Dashboard mit:
- Gesamt-Statistiken (Sessions, Dokumente, Erfolgsrate)
- Aktivitäts-Timeline
- Fehler-Trends
- Model-Performance (Opus vs Sonnet)
- Learning-System Adoption
- Durchschnittliche Response-Zeiten

**Zugriff:**
```
GET /analytics?days=30
```

---

## 💡 Use Cases

### 1. Debugging
*"Warum hat die Analyse bei Session X nicht funktioniert?"*
→ Query `activity_logs` für diese Session → Siehe alle Events + Timings

### 2. Performance-Optimierung
*"Welche Dokumente verursachen Timeouts?"*
→ Query Analyse-Dauer + Fehler-Logs → Identifiziere Problem-PDFs

### 3. User-Verhalten
*"Welche Features werden am meisten genutzt?"*
→ Group by event_type → Siehe Häufigkeiten

### 4. Learning-System Evaluation
*"Werden die Vorschläge akzeptiert?"*
→ Query `learning_suggestions` → Acceptance-Rate

### 5. Model-Vergleich
*"Ist Opus besser als Sonnet für unseren Use-Case?"*
→ Query Chat-Logs → Vergleiche Antwort-Qualität + Dauer

---

## 🔐 Privacy

**Was wird NICHT geloggt:**
- ❌ Passwörter
- ❌ Vollständige PDF-Inhalte
- ❌ Persönliche Daten aus Dokumenten
- ❌ IP-Adressen (für Prototype)

**Was wird geloggt:**
- ✅ Event-Typen und Timings
- ✅ Dateinamen (für Debugging)
- ✅ Chat-Messages (für Improvement)
- ✅ User-Agent (Browser-Info)
- ✅ Fehler-Details

**GDPR-Konform:** Alle Daten sind in Supabase (EU-Region)

---

*Erstellt: 18.01.2026, 03:30*
