"""
Revipro Reconciliation Engine - PDF Analysis and Tax Audit
Version 5.0 - With Claude Sonnet 4 AI Integration
Supports: Tax Statements (JA, SR, Nachsteuern), FiBu Statements, Annual Report Excerpts (ER/Bilanz)

Key Features:
- Hybrid extraction: Regex first, Claude AI fallback
- Intelligent analysis and explanations
- Automatic anomaly detection
"""
import re
import os
import asyncio
import threading
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pdfplumber
import io

# Claude AI Integration
from anthropic import Anthropic
from supabase import create_client, Client

# Initialize Anthropic client
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable is required")
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Initialize Supabase client with Service Role Key
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://poeulzxkjcxeszfcsiks.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBvZXVsenhramN4ZXN6ZmNzaWtzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2ODY1ODE5NCwiZXhwIjoyMDg0MjM0MTk0fQ.bzXwJlQMGmlNJJICob_X213YlC7oFiY11ZRRT060e7c")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Session storage for chat history and audit context (local cache, backed by Supabase)
import uuid
from datetime import datetime
import time

chat_sessions: Dict[str, Dict] = {}  # session_id -> {messages: [], audit_context: {}, raw_files: [], created_at: datetime}

# Store raw file bytes for reprocessing (local cache)
file_storage: Dict[str, List[tuple]] = {}  # session_id -> [(filename, bytes), ...]


# ============== Activity Logging ==============

async def log_activity(
    session_id: str = None,
    event_type: str = None,
    event_category: str = None,
    data: dict = None,
    duration_ms: int = None,
    status: str = "success",
    error_message: str = None,
    user_agent: str = None,
    ip_address: str = None
):
    """Log activity to Supabase for analytics and debugging."""
    try:
        log_data = {
            "session_id": session_id,
            "event_type": event_type,
            "event_category": event_category,
            "data": data or {},
            "duration_ms": duration_ms,
            "status": status,
            "error_message": error_message,
            "user_agent": user_agent,
            "ip_address": ip_address,
            "metadata": {}
        }
        
        # Fire-and-forget logging (don't block main flow)
        def log_bg():
            try:
                supabase.table("activity_logs").insert(log_data).execute()
            except Exception as e:
                print(f"Logging error (non-critical): {e}")
        
        threading.Thread(target=log_bg, daemon=True).start()
    except Exception as e:
        print(f"Log preparation error: {e}")


async def log_error(
    session_id: str = None,
    error_type: str = None,
    error_message: str = None,
    stack_trace: str = None,
    context: dict = None
):
    """Log errors for debugging."""
    try:
        error_data = {
            "session_id": session_id,
            "error_type": error_type,
            "error_message": error_message,
            "stack_trace": stack_trace,
            "context": context or {},
            "resolved": False
        }
        
        def log_bg():
            try:
                supabase.table("error_logs").insert(error_data).execute()
            except Exception as e:
                print(f"Error logging error: {e}")
        
        threading.Thread(target=log_bg, daemon=True).start()
    except Exception as e:
        print(f"Error log preparation error: {e}")


# ============== Helper Functions ==============

def detect_organization_name(tax_docs: List[dict], fibu_docs: List[dict]) -> str:
    """
    Auto-detect organization name from documents.
    Look for common patterns in filenames or extracted text.
    """
    # Check filenames for organization names
    all_files = []
    for doc in tax_docs + fibu_docs:
        filename = doc.get("filename", "")
        all_files.append(filename)
    
    # Common patterns
    gemeinde_patterns = [
        r"(Gemeinde|Politische Gemeinde)\s+(\w+)",
        r"(\w+)\s+Gemeinde",
        r"(Lufingen|Niederhasli|Bülach|Winterthur|Zürich)",  # Known municipalities
    ]
    
    kirche_patterns = [
        r"(Reformierte|Katholische|ref\.|kath\.)\s+Kirche\s+(\w+)?",
        r"Kirche\s+(\w+)",
    ]
    
    for filename in all_files:
        # Try Gemeinde patterns
        for pattern in gemeinde_patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                # Return the most specific match
                if match.lastindex and match.lastindex >= 2:
                    return f"Gemeinde {match.group(match.lastindex)}"
                return match.group(0)
        
        # Try Kirche patterns
        for pattern in kirche_patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return match.group(0)
    
    # Default
    return "Steuerprüfung"


# ============== Supabase Helper Functions ==============

async def save_session_to_supabase(session_id: str, organization_type: str = None, column_preference: str = None):
    """Create or update a session in Supabase."""
    try:
        data = {
            "id": session_id,
            "organization_type": organization_type,
            "column_preference": column_preference,
            "status": "active"
        }
        supabase.table("sessions").upsert(data).execute()
        print(f"Session saved to Supabase: {session_id}")
    except Exception as e:
        print(f"Error saving session to Supabase: {e}")


async def save_document_to_supabase(session_id: str, filename: str, file_bytes: bytes, doc_type: str, extracted_data: dict):
    """Save document metadata and file to Supabase."""
    try:
        # Upload file to storage
        file_path = f"{session_id}/{filename}"
        supabase.storage.from_("documents").upload(file_path, file_bytes, {"content-type": "application/pdf"})
        
        # Save metadata to database
        data = {
            "session_id": session_id,
            "filename": filename,
            "file_path": file_path,
            "file_size": len(file_bytes),
            "document_type": doc_type,
            "extracted_data": extracted_data
        }
        supabase.table("documents").insert(data).execute()
        print(f"Document saved to Supabase: {filename}")
    except Exception as e:
        print(f"Error saving document to Supabase: {e}")


async def save_chat_message_to_supabase(session_id: str, role: str, content: str, message_type: str = "text", metadata: dict = None):
    """Save a chat message to Supabase."""
    try:
        data = {
            "session_id": session_id,
            "role": role,
            "content": content,
            "message_type": message_type,
            "metadata": metadata or {}
        }
        supabase.table("chat_messages").insert(data).execute()
    except Exception as e:
        print(f"Error saving chat message to Supabase: {e}")


async def save_audit_results_to_supabase(session_id: str, results: List[dict]):
    """Save audit results to Supabase."""
    try:
        for result in results:
            summary = result.get("summary", {})
            data = {
                "session_id": session_id,
                "rule": summary.get("rule"),
                "description": summary.get("description"),
                "status": summary.get("status"),
                "tax_total": summary.get("tax_total"),
                "fibu_total": summary.get("fibu_total"),
                "difference": summary.get("difference"),
                "details": result.get("details")
            }
            supabase.table("audit_results").insert(data).execute()
        print(f"Audit results saved to Supabase for session: {session_id}")
    except Exception as e:
        print(f"Error saving audit results to Supabase: {e}")


async def get_session_documents(session_id: str) -> List[dict]:
    """Get all documents for a session from Supabase."""
    try:
        result = supabase.table("documents").select("*").eq("session_id", session_id).execute()
        return result.data
    except Exception as e:
        print(f"Error getting documents from Supabase: {e}")
        return []


async def get_chat_history(session_id: str) -> List[dict]:
    """Get chat history for a session from Supabase."""
    try:
        result = supabase.table("chat_messages").select("*").eq("session_id", session_id).order("created_at").execute()
        return result.data
    except Exception as e:
        print(f"Error getting chat history from Supabase: {e}")
        return []


async def get_client_knowledge(client_name: str) -> Dict:
    """Get all learned knowledge for a client."""
    try:
        result = supabase.table("client_knowledge").select("*").eq("client_name", client_name).eq("confirmed_by_user", True).execute()
        
        knowledge = {
            "column_preferences": [],
            "typical_accounts": [],
            "known_anomalies": [],
            "document_formats": [],
            "custom_rules": []
        }
        
        for item in result.data:
            k_type = item["knowledge_type"]
            if k_type == "column_preference":
                knowledge["column_preferences"].append(item["value"])
            elif k_type == "account_pattern":
                knowledge["typical_accounts"].append(item["value"])
            elif k_type == "anomaly":
                knowledge["known_anomalies"].append(item["value"])
            elif k_type == "document_format":
                knowledge["document_formats"].append(item["value"])
            elif k_type == "custom":
                knowledge["custom_rules"].append(item["value"])
        
        return knowledge
    except Exception as e:
        print(f"Error getting client knowledge: {e}")
        return {}


async def detect_learning_opportunities(session_id: str, client_name: str, tax_docs: List, fibu_docs: List, audit_results: List) -> List[Dict]:
    """
    Detect patterns that could be learned.
    Returns list of suggestions for user confirmation.
    """
    suggestions = []
    
    # 1. Detect column preference (if user mentioned it in chat or if we see consistent pattern)
    # Check if specific column appears in multiple documents
    column_mentions = {}
    for doc in tax_docs:
        # This would need more sophisticated detection
        # For now, placeholder
        pass
    
    # 2. Detect recurring account numbers
    account_numbers = set()
    for doc in fibu_docs:
        acc = doc.get("account")
        if acc:
            account_numbers.add(acc)
    
    if len(account_numbers) >= 2:
        suggestions.append({
            "type": "account_pattern",
            "title": f"Typische Konten für {client_name}",
            "description": f"Die Konten {', '.join(sorted(account_numbers))} werden regelmässig verwendet. Soll ich dies speichern?",
            "knowledge": {
                "accounts": list(account_numbers),
                "frequency": "regular"
            }
        })
    
    # 3. Detect recurring differences (anomalies)
    for result in audit_results:
        summary = result.get("summary", {})
        if summary.get("status") == "MISMATCH" and summary.get("difference", 0) > 0:
            diff = summary.get("difference")
            rule = summary.get("rule")
            
            # Check if this is a known pattern (e.g., always ~50 CHF difference for late fees)
            if 40 <= diff <= 60:
                suggestions.append({
                    "type": "anomaly",
                    "title": f"Wiederkehrende Differenz bei {rule}",
                    "description": f"Es wurde eine Differenz von CHF {diff:.2f} festgestellt. Dies könnte auf Verzugszinsen hindeuten. Soll ich dies als bekanntes Muster speichern?",
                    "knowledge": {
                        "rule": rule,
                        "typical_difference": diff,
                        "likely_cause": "Verzugszinsen"
                    }
                })
    
    # 4. Detect document format patterns
    doc_types = set()
    for doc in tax_docs + fibu_docs:
        dtype = doc.get("type")
        if dtype:
            doc_types.add(dtype)
    
    if len(doc_types) >= 3:
        suggestions.append({
            "type": "document_format",
            "title": f"Standard-Dokumentenset für {client_name}",
            "description": f"Typischerweise werden folgende Dokumenttypen verwendet: {', '.join(sorted(doc_types))}. Speichern?",
            "knowledge": {
                "expected_types": list(doc_types)
            }
        })
    
    return suggestions


async def save_learning_suggestions(session_id: str, client_name: str, suggestions: List[Dict]):
    """Save learning suggestions to database for user review."""
    try:
        for suggestion in suggestions:
            data = {
                "session_id": session_id,
                "client_name": client_name,
                "suggestion_type": suggestion["type"],
                "title": suggestion["title"],
                "description": suggestion["description"],
                "proposed_knowledge": suggestion["knowledge"],
                "status": "pending"
            }
            supabase.table("learning_suggestions").insert(data).execute()
        print(f"Saved {len(suggestions)} learning suggestions for {client_name}")
    except Exception as e:
        print(f"Error saving learning suggestions: {e}")

app = FastAPI(title="Revipro Reconciliation Engine", version="5.0.0")

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for prototype
    allow_credentials=False,  # Must be False when allow_origins is *
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool for CPU-bound tasks
executor = ThreadPoolExecutor(max_workers=4)


# ============== Response Models ==============

class TaxItem(BaseModel):
    year: str
    amount: float
    source: str
    label: Optional[str] = None
    doc_type: Optional[str] = None


class FibuItem(BaseModel):
    account: str
    amount: float
    source: str
    label: Optional[str] = None


class AuditDetails(BaseModel):
    tax_items: List[TaxItem]
    fibu_items: List[FibuItem]


class AuditSummary(BaseModel):
    rule: str
    description: str
    status: str
    difference: float
    tax_total: Optional[float]
    fibu_total: Optional[float]
    hint: Optional[str] = None


class AuditResult(BaseModel):
    summary: AuditSummary
    details: AuditDetails


class AIInsight(BaseModel):
    summary: str
    findings: List[str]
    recommendations: List[str]
    confidence: str


class AnalysisResponse(BaseModel):
    results: List[AuditResult]
    files_processed: int
    tax_files: int
    fibu_files: int
    annual_report_files: int
    ai_insight: Optional[AIInsight] = None
    session_id: Optional[str] = None  # For chat continuity
    raw_extractions: Optional[Dict] = None  # Raw data for re-analysis


class ReprocessRequest(BaseModel):
    session_id: str
    column_name: Optional[str] = None  # e.g., "Politische Gemeinde", "ref. Kirche"
    organization_type: Optional[str] = None  # "gemeinde", "kirche", "schule"


class LearningSuggestion(BaseModel):
    id: str
    session_id: str
    client_name: str
    suggestion_type: str
    title: str
    description: str
    proposed_knowledge: Dict
    status: str = "pending"


# ============== Chat Models ==============

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: str
    include_audit_context: bool = True
    model: str = "opus"  # "opus" or "sonnet"


class ChatResponse(BaseModel):
    response: str
    session_id: str
    suggestions: List[str] = []  # Quick reply suggestions


# ============== Claude AI Service ==============

async def analyze_with_claude(
    audit_results: List[Dict],
    tax_docs: List[Dict],
    fibu_docs: List[Dict],
    user_context: Optional[str] = None
) -> AIInsight:
    """
    Use Claude Sonnet 4 to analyze audit results and provide intelligent insights.
    """
    try:
        # Prepare context for Claude
        context = f"""Du bist ein Experte für Schweizer Gemeindesteuerprüfung und Buchhaltung.

Analysiere die folgenden Prüfungsergebnisse und gib eine professionelle Einschätzung.

"""
        # Add user context if provided
        if user_context:
            context += f"""## Zusätzlicher Kontext vom Benutzer:
{user_context}

"""

        context += """## Prüfungsergebnisse:

"""
        for result in audit_results:
            summary = result.get("summary", {})
            context += f"""
### {summary.get('rule', 'Regel')}: {summary.get('description', '')}
- Status: {summary.get('status', 'Unbekannt')}
- Steuerabrechnung (Soll): CHF {summary.get('tax_total', 'N/A')}
- FiBu/Bilanz (Ist): CHF {summary.get('fibu_total', 'N/A')}
- Differenz: CHF {summary.get('difference', 0)}
"""

        context += """
## Extrahierte Steuerdokumente:
"""
        for doc in tax_docs[:10]:  # Limit to avoid token overflow
            context += f"- {doc.get('filename', 'Unknown')}: Typ={doc.get('type', '?')}, Jahr={doc.get('year', '?')}, Restanzen={doc.get('restanzen_gemeinde', 'N/A')}, Negativ={doc.get('is_negative', False)}\n"

        context += """
## Extrahierte FiBu-Dokumente:
"""
        for doc in fibu_docs[:10]:
            context += f"- {doc.get('filename', 'Unknown')}: Konto={doc.get('account', '?')}, Saldo={doc.get('saldo', 'N/A')}\n"

        # Call Claude Opus 4.5
        message = anthropic_client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": f"""{context}

Bitte analysiere diese Daten und antworte im folgenden JSON-Format (nur JSON, keine anderen Texte):

{{
    "summary": "Eine kurze Zusammenfassung der Prüfung in 1-2 Sätzen",
    "findings": [
        "Feststellung 1",
        "Feststellung 2",
        "..."
    ],
    "recommendations": [
        "Empfehlung 1",
        "Empfehlung 2",
        "..."
    ],
    "confidence": "hoch" oder "mittel" oder "niedrig"
}}

Fokussiere auf:
1. Ob die Verbuchung korrekt ist
2. Mögliche Ursachen für Differenzen
3. Konkrete Prüfungsempfehlungen
4. Auffälligkeiten oder Anomalien"""
                }
            ]
        )

        # Parse response
        response_text = message.content[0].text.strip()
        
        # Try to extract JSON from response
        import json
        
        # Handle potential markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        try:
            insight_data = json.loads(response_text)
            return AIInsight(
                summary=insight_data.get("summary", "Analyse abgeschlossen."),
                findings=insight_data.get("findings", []),
                recommendations=insight_data.get("recommendations", []),
                confidence=insight_data.get("confidence", "mittel")
            )
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return AIInsight(
                summary=response_text[:200] if len(response_text) > 200 else response_text,
                findings=["Siehe Zusammenfassung für Details."],
                recommendations=["Manuelle Überprüfung empfohlen."],
                confidence="niedrig"
            )

    except Exception as e:
        print(f"Claude AI Error: {e}")
        return AIInsight(
            summary=f"KI-Analyse nicht verfügbar: {str(e)[:100]}",
            findings=[],
            recommendations=["Bitte prüfen Sie die Ergebnisse manuell."],
            confidence="niedrig"
        )


async def extract_with_claude_fallback(text: str, filename: str, extraction_type: str) -> Optional[Dict]:
    """
    Use Claude as fallback for difficult document extraction.
    """
    try:
        prompt = ""
        if extraction_type == "fibu_saldo":
            prompt = f"""Analysiere den folgenden Kontoauszug-Text und extrahiere den Schlusssaldo.

Dateiname: {filename}
Text (erste 3000 Zeichen):
{text[:3000]}

Antworte NUR im JSON-Format:
{{"account": "1012.00 oder 2002.00 oder 2006.10", "saldo": 12345.67, "confidence": "hoch/mittel/niedrig"}}

Falls du den Saldo nicht finden kannst, antworte: {{"account": null, "saldo": null, "confidence": "niedrig"}}"""

        elif extraction_type == "tax_restanzen":
            prompt = f"""Analysiere den folgenden Steuerabschluss-Text und extrahiere die "Total Restanzen" für die Spalte "Politische Gemeinde".

Dateiname: {filename}
Text (erste 3000 Zeichen):
{text[:3000]}

Wichtig:
- Suche nach "Total Restanzen" (nicht "Restanzenvortrag")
- Der Wert kann positiv oder negativ sein
- Negative Werte gehen auf Konto 2002 (Verpflichtungen)

Antworte NUR im JSON-Format:
{{"restanzen": 12345.67, "is_negative": true/false, "year": "2024", "confidence": "hoch/mittel/niedrig"}}"""

        if not prompt:
            return None

        message = anthropic_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text.strip()
        
        # Clean up response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        import json
        return json.loads(response_text)

    except Exception as e:
        print(f"Claude extraction fallback error: {e}")
        return None


# ============== PDF Extraction Functions ==============

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract all text from a PDF file."""
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
    return text


def extract_tables_from_pdf(file_bytes: bytes) -> List[List[List[str]]]:
    """Extract tables from a PDF file for better column parsing."""
    tables = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_tables = page.extract_tables()
                if page_tables:
                    tables.extend(page_tables)
    except Exception as e:
        print(f"Error extracting PDF tables: {e}")
    return tables


def detect_tax_document_type(text: str, filename: str) -> str:
    """Detect tax document type."""
    text_lower = text.lower()
    filename_lower = filename.lower()
    
    # IGNORE: Quellensteuer documents (QVO)
    if "quellensteuer" in text_lower or "qvo" in filename_lower:
        print(f"    Ignoring Quellensteuer document: {filename}")
        return "quellensteuer"  # Will be ignored in processing
    
    # PRIORITY 1: FiBu Kontoauszug
    if "fibu" in filename_lower and "konto" in filename_lower:
        return "fibu"
    if re.search(r'^\d+-fibu', filename_lower):
        return "fibu"
    if "kontoauszug" in text_lower:
        return "fibu"
    
    # Combined FiBu document (contains multiple accounts)
    if "konti" in filename_lower or "restanzen" in filename_lower:
        # Check if it contains FiBu account numbers
        if re.search(r'\b(1012\.00|2002\.00)\b', text):
            return "fibu_combined"
    
    # Check for FiBu indicators in text
    if "fibukonto" in text_lower or "fibukontoblatt" in text_lower:
        return "fibu_combined"
    if "forderungen allgemeine gemeindesteuern" in text_lower:
        return "fibu_combined"
    if "verpflichtungen aus allgemeinen gemeindesteuern" in text_lower:
        return "fibu_combined"
    
    # PRIORITY 2: Tax documents by filename pattern
    if "nachsteuer" in filename_lower and "fibu" not in filename_lower:
        return "NAST"
    if re.search(r'sr_\d{4}_\d{4}', filename_lower):
        return "SR"
    if re.search(r'ja_\d{4}_\d{4}', filename_lower):
        return "JA"
    
    # PRIORITY 3: Tax documents by text content
    if "abrechnung über den ertrag von nachsteuern" in text_lower:
        return "NAST"
    if "nachsteuern" in text_lower and "total restanzen nachsteuern" in text_lower:
        return "NAST"
    if "jahresabschluss" in text_lower and "fibu" not in filename_lower:
        return "JA"
    if "steuerrestanz" in text_lower:
        return "SR"
    
    # PRIORITY 4: Annual Report pages
    if "erfolgsrechnung" in text_lower and "9100" in text:
        return "erfolgsrechnung"
    if "bilanz" in text_lower and "fibu" not in filename_lower:
        if "bestand per" in text_lower or "31.12." in text:
            return "bilanz"
    
    # PRIORITY 5: General tax statement detection
    if "gemowing" in text_lower or "steuerabschluss" in text_lower:
        year_match = re.search(r'(\d{4})_(\d{4})', filename)
        if year_match:
            if year_match.group(1) == year_match.group(2):
                return "JA"
            else:
                return "SR"
        return "JA"
    
    if "gemeindesteuern" in text_lower and "total restanzen" in text_lower:
        year_match = re.search(r'(\d{4})_(\d{4})', filename)
        if year_match:
            if year_match.group(1) == year_match.group(2):
                return "JA"
            else:
                return "SR"
        return "JA"
    
    return "unknown"


def extract_year_from_text(text: str, filename: str = "") -> str:
    """Extract the TAX year from document text or filename."""
    year_match = re.search(r'_(\d{4})_(\d{4})', filename)
    if year_match:
        return year_match.group(2)
    
    year_patterns = [
        r'(?:Rechnungsjahr|Rechnung|Jahr|Year|Periode|Period|Steuerperiode)[:\s]*(\d{4})',
        r'(?:per|vom|from)\s*\d{1,2}\.\d{1,2}\.(\d{4})',
        r'31\.12\.(\d{4})',
        r'\b(20\d{2})\b',
    ]
    
    for pattern in year_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return "2024"


def extract_monetary_value(text: str) -> Optional[float]:
    """Extract a monetary value from text."""
    if not text:
        return None
        
    text = str(text).strip()
    if len(text) < 2:
        return None
    
    is_negative = False
    if text.startswith('-') or text.startswith('(') or text.endswith('-') or text.endswith(')'):
        is_negative = True
    
    text = re.sub(r'[CHF\s\(\)\-]', '', text)
    
    if re.match(r'^\d{4}\.\d{2}$', text):
        return None
    if '%' in text:
        return None
    
    match = re.search(r'([\d\',.]+)', text)
    if match:
        number_str = match.group(1)
        number_str = number_str.replace("'", "")
        
        if ',' in number_str and '.' not in number_str:
            number_str = number_str.replace(",", ".")
        elif ',' in number_str and '.' in number_str:
            number_str = number_str.replace(",", "")
        
        try:
            value = float(number_str)
            return -value if is_negative else value
        except ValueError:
            pass
    
    return None


# ============== Tax Statement Parsing ==============

def find_column_index_for_gemeinde(headers: List[str], target: str = "Politische Gemeinde") -> int:
    """Find the column index for the target Gemeinde."""
    for i, header in enumerate(headers):
        if header and target.lower() in str(header).lower():
            return i
    return 4


def extract_value_from_row(row: List[str], column_index: int) -> Optional[float]:
    """Extract monetary value from a specific column in a row."""
    if row and len(row) > column_index:
        cell = row[column_index]
        if cell:
            return extract_monetary_value(str(cell))
    return None


def parse_tax_statement_tables(tables: List[List[List[str]]], doc_type: str, filename: str) -> dict:
    """Parse tax statement tables (JA, SR, NAST)."""
    data = {
        "filename": filename,
        "type": doc_type,
        "year": "Unknown",
        "restanzen_gemeinde": None,
        "restanzenvortrag_gemeinde": None,
        "is_negative": False,
        "raw_restanzen": None,
    }
    
    gemeinde_col = 4
    
    for table in tables:
        for row in table[:5]:
            for i, cell in enumerate(row):
                if cell and "politische gemeinde" in str(cell).lower():
                    gemeinde_col = i
                    break
        
        for row in table:
            if not row or not row[0]:
                continue
                
            first_cell = str(row[0]).strip()
            row_num = None
            try:
                row_num = int(first_cell)
            except ValueError:
                pass
            
            row_text = ' '.join([str(c) if c else '' for c in row]).lower()
            
            if row_num == 51 or (doc_type == "SR" and "total restanzen" in row_text and "vortrag" not in row_text):
                value = extract_value_from_row(row, gemeinde_col)
                if value is not None:
                    data["raw_restanzen"] = value
                    data["restanzen_gemeinde"] = abs(value)
                    data["is_negative"] = value < 0
                    print(f"    Found SR Zeile 51: {value}, negative: {value < 0}")
                    
            elif row_num == 45 or "total restanzen" in row_text:
                if "vortrag" in row_text:
                    value = extract_value_from_row(row, gemeinde_col)
                    if value is not None:
                        data["restanzenvortrag_gemeinde"] = value
                elif doc_type == "JA":
                    value = extract_value_from_row(row, gemeinde_col)
                    if value is not None:
                        data["raw_restanzen"] = value
                        data["restanzen_gemeinde"] = abs(value)
                        data["is_negative"] = value < 0
                        print(f"    Found JA Zeile 45: {value}, negative: {value < 0}")
            
            elif row_num == 44 or (doc_type == "NAST" and "total restanzen nachsteuern" in row_text):
                value = extract_value_from_row(row, gemeinde_col)
                if value is not None:
                    data["raw_restanzen"] = value
                    data["restanzen_gemeinde"] = abs(value)
                    data["is_negative"] = value < 0
                    print(f"    Found NAST Zeile 44: {value}")
            
            elif row_num == 38 or "restanzenvortrag inkl. zinsen" in row_text:
                value = extract_value_from_row(row, gemeinde_col)
                if value is not None:
                    data["restanzenvortrag_gemeinde"] = value
                    if data["restanzen_gemeinde"] is None and doc_type == "NAST":
                        data["raw_restanzen"] = value
                        data["restanzen_gemeinde"] = abs(value)
                        data["is_negative"] = value < 0
    
    return data


def extract_tax_statement_data_v2(text: str, tables: List, filename: str, doc_type: str) -> dict:
    """Enhanced extraction for Tax Statements."""
    year = extract_year_from_text(text, filename)
    data = parse_tax_statement_tables(tables, doc_type, filename)
    data["year"] = year
    
    if data["restanzen_gemeinde"] is None:
        lines = text.split('\n')
        for line in lines:
            line_lower = line.lower()
            
            if "total restanzen" in line_lower and "vortrag" not in line_lower:
                line_has_negative = '-' in line or '(' in line
                values = re.findall(r"[\d',.]+", line)
                
                if len(values) >= 5:
                    raw_value_str = values[4]
                    value_pos = line.find(raw_value_str)
                    is_negative = False
                    if value_pos > 0:
                        prefix = line[max(0, value_pos-5):value_pos]
                        if '-' in prefix:
                            is_negative = True
                    
                    target_value = extract_monetary_value(raw_value_str)
                    if target_value is not None:
                        data["raw_restanzen"] = -target_value if is_negative else target_value
                        data["restanzen_gemeinde"] = abs(target_value)
                        data["is_negative"] = is_negative
                        print(f"    Text fallback: {target_value}, negative: {is_negative}")
                        break
    
    # Filename hint for negative detection
    if data["restanzen_gemeinde"] is not None and not data["is_negative"]:
        filename_lower = filename.lower()
        if "2002" in filename_lower or "minusbetrag" in filename_lower:
            if "1012" not in filename_lower:
                data["is_negative"] = True
                print(f"    Filename hint: setting is_negative=True")
    
    return data


# ============== FiBu Statement Parsing ==============

def extract_fibu_statement_data(text: str, tables: List, filename: str) -> dict:
    """Extract data from a FiBu Statement (Kontoauszug)."""
    data = {
        "filename": filename,
        "type": "fibu",
        "account": None,
        "saldo": None,
    }
    
    lines = text.split('\n')
    
    # Detect account number
    for pattern_source in [filename] + lines[:15]:
        match = re.search(r'\b(1012\.00|2002\.00|2006\.10)\b', pattern_source)
        if match:
            data["account"] = match.group(1)
            print(f"    Found account: {data['account']}")
            break
    
    # Strategy 1: Table extraction
    for table in tables:
        for row in reversed(table):
            if not row:
                continue
            
            row_text = ' '.join([str(c) if c else '' for c in row]).lower()
            
            if "total" in row_text or "anzahl buchungen" in row_text:
                for cell in row:
                    if cell:
                        value = extract_monetary_value(str(cell))
                        if value is not None and value > 100:
                            data["saldo"] = value
                
                if data["saldo"] is not None:
                    print(f"    Found Saldo from table: {data['saldo']}")
                    break
    
    # Strategy 2: Text-based - look for last saldo value
    if data["saldo"] is None:
        saldo_values = []
        for line in lines:
            if "saldo" in line.lower() and "buchungstext" in line.lower():
                continue
            values = re.findall(r"[\d',.]+", line)
            if len(values) >= 3:
                for v in values:
                    value = extract_monetary_value(v)
                    if value is not None and value > 100:
                        saldo_values.append(value)
        
        if saldo_values:
            data["saldo"] = saldo_values[-1]
            print(f"    Found Saldo from text: {data['saldo']}")
    
    # Strategy 3: Look for "Total:" row
    if data["saldo"] is None:
        for line in lines:
            if "total:" in line.lower() or "saldo buchungsjahr" in line.lower():
                values = re.findall(r"[\d',.]+", line)
                if len(values) >= 1:
                    for v in reversed(values):
                        value = extract_monetary_value(v)
                        if value is not None and value > 100:
                            data["saldo"] = value
                            print(f"    Found Saldo from Total line: {value}")
                            break
                    if data["saldo"] is not None:
                        break
    
    return data


# ============== Combined FiBu Document Parsing ==============

def extract_combined_fibu_data(text: str, tables: List, filename: str) -> List[dict]:
    """
    Extract data from a combined FiBu document that contains multiple accounts.
    Returns a list of FiBu documents, one for each account found.
    
    Format: The document has sections for each account with Startsaldo and Endsaldo.
    We need the LAST value in the Endsaldo row (the Saldo column).
    """
    results = []
    lines = text.split('\n')
    
    current_account = None
    account_data = {}  # Store data per account
    
    print(f"    Parsing combined FiBu document: {filename}")
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        # Detect account section headers
        if "1012.00" in line:
            if "forderungen" in line_lower or (i+1 < len(lines) and "startsaldo" in lines[i+1].lower()):
                current_account = "1012.00"
                account_data[current_account] = {"startsaldo": None, "endsaldo": None}
                print(f"    Found account section: 1012.00")
        
        if "2002.00" in line:
            if "verpflichtungen" in line_lower or (i+1 < len(lines) and "startsaldo" in lines[i+1].lower()):
                current_account = "2002.00"
                account_data[current_account] = {"startsaldo": None, "endsaldo": None}
                print(f"    Found account section: 2002.00")
        
        # Look for Endsaldo line - this is the key!
        if current_account and "endsaldo" in line_lower:
            # The Endsaldo line typically ends with the final saldo value
            # Format: "Endsaldo | | | | 5'253'278.26 | 5'485'692.48 | 5'248'958.26"
            # The LAST value is the actual saldo
            values = re.findall(r'-?[\d\']+(?:\.\d{2})?', line)
            print(f"    Endsaldo line for {current_account}: '{line.strip()}'")
            print(f"    Extracted values: {values}")
            
            if values:
                # Get the last non-zero value (the actual saldo)
                for v in reversed(values):
                    value = extract_monetary_value(v)
                    if value is not None:
                        account_data[current_account]["endsaldo"] = abs(value)
                        print(f"    ✓ Endsaldo for {current_account}: CHF {abs(value):,.2f}")
                        break
                
                # If all values are 0, the saldo is 0
                if account_data[current_account]["endsaldo"] is None:
                    account_data[current_account]["endsaldo"] = 0.0
                    print(f"    ✓ Endsaldo for {current_account}: CHF 0.00 (cleared)")
            
            # Reset current account after finding endsaldo
            current_account = None
    
    # Build results from account data
    for account, data in account_data.items():
        if data["endsaldo"] is not None:
            results.append({
                "filename": filename,
                "type": "fibu",
                "account": account,
                "saldo": data["endsaldo"],
            })
    
    # Fallback: table-based extraction if text parsing found nothing
    if not results:
        print(f"    Text parsing found no results, trying table extraction...")
        for table in tables:
            current_account = None
            for row in table:
                if not row:
                    continue
                    
                row_text = ' '.join([str(c) if c else '' for c in row]).lower()
                
                # Detect account section
                if "1012.00" in row_text and "forderungen" in row_text:
                    current_account = "1012.00"
                elif "2002.00" in row_text and "verpflichtungen" in row_text:
                    current_account = "2002.00"
                
                # Look for Endsaldo row
                if current_account and "endsaldo" in row_text:
                    # Get the last cell with a value
                    for cell in reversed(row):
                        if cell:
                            value = extract_monetary_value(str(cell))
                            if value is not None:
                                results.append({
                                    "filename": filename,
                                    "type": "fibu",
                                    "account": current_account,
                                    "saldo": abs(value),
                                })
                                print(f"    Table: Endsaldo for {current_account}: CHF {abs(value):,.2f}")
                                current_account = None
                                break
                    
                    # If no value found, it's 0
                    if current_account:
                        results.append({
                            "filename": filename,
                            "type": "fibu",
                            "account": current_account,
                            "saldo": 0.0,
                        })
                        print(f"    Table: Endsaldo for {current_account}: CHF 0.00")
                        current_account = None
    
    print(f"    Combined FiBu results: {results}")
    return results


# ============== Annual Report Parsing ==============

def extract_erfolgsrechnung_data(text: str, tables: List, filename: str) -> dict:
    """Extract data from Erfolgsrechnung (Income Statement)."""
    data = {
        "filename": filename,
        "type": "erfolgsrechnung",
        "year": extract_year_from_text(text, filename),
        "account_9100_total": None,
        "account_9100_items": [],
    }
    
    lines = text.split('\n')
    total_9100 = 0.0
    found_items = []
    
    for line in lines:
        match = re.match(r'^(9100\.\d{4}(?:\.\d{2})?)\s+(.+)', line)
        if match:
            account = match.group(1)
            rest_of_line = match.group(2)
            parts = rest_of_line.split()
            for part in parts:
                value = extract_monetary_value(part)
                if value is not None:
                    total_9100 += value
                    found_items.append({"account": account, "amount": value})
                    break
    
    for table in tables:
        for row in table:
            if row and len(row) > 0 and row[0]:
                first_cell = str(row[0]).strip()
                if first_cell.startswith("9100."):
                    for cell in row[1:]:
                        if cell:
                            value = extract_monetary_value(str(cell))
                            if value is not None:
                                if not any(item["account"] == first_cell for item in found_items):
                                    total_9100 += value
                                    found_items.append({"account": first_cell, "amount": value})
                                break
    
    if found_items:
        data["account_9100_total"] = round(total_9100, 2)
        data["account_9100_items"] = found_items
    
    return data


def extract_bilanz_data(text: str, tables: List, filename: str) -> dict:
    """Extract data from Bilanz (Balance Sheet)."""
    data = {
        "filename": filename,
        "type": "bilanz",
        "year": extract_year_from_text(text, filename),
        "account_1012": None,
        "account_2002": None,
        "account_2006_10": None,
    }
    
    lines = text.split('\n')
    
    for line in lines:
        if re.search(r'\b1012\.\d{2}\b', line):
            values = re.findall(r"[\d',.]+", line)
            for v in reversed(values):
                value = extract_monetary_value(v)
                if value is not None and value > 100:
                    if data["account_1012"] is None:
                        data["account_1012"] = value
                    break
        
        if re.search(r'\b2002\.\d{2}\b', line):
            values = re.findall(r"[\d',.]+", line)
            for v in reversed(values):
                value = extract_monetary_value(v)
                if value is not None and value > 100:
                    if data["account_2002"] is None:
                        data["account_2002"] = value
                    break
        
        if "2006.10" in line:
            values = re.findall(r"[\d',.]+", line)
            for v in reversed(values):
                value = extract_monetary_value(v)
                if value is not None and value > 100:
                    data["account_2006_10"] = value
                    break
    
    return data


# ============== Main Parsing Function ==============

def parse_pdf(file_bytes: bytes, filename: str) -> dict:
    """Parse a PDF file and extract relevant data."""
    text = extract_text_from_pdf(file_bytes)
    tables = extract_tables_from_pdf(file_bytes)
    doc_type = detect_tax_document_type(text, filename)
    
    print(f"  Detected document type: {doc_type}")
    
    if doc_type in ["JA", "SR", "NAST"]:
        return extract_tax_statement_data_v2(text, tables, filename, doc_type)
    elif doc_type == "fibu":
        return extract_fibu_statement_data(text, tables, filename)
    elif doc_type == "fibu_combined":
        # Returns a list of documents
        return {"type": "fibu_combined", "documents": extract_combined_fibu_data(text, tables, filename)}
    elif doc_type == "erfolgsrechnung":
        return extract_erfolgsrechnung_data(text, tables, filename)
    elif doc_type == "bilanz":
        return extract_bilanz_data(text, tables, filename)
    
    if "gemeindesteuern" in text.lower() and "total restanzen" in text.lower():
        print(f"  Fallback: treating as JA")
        return extract_tax_statement_data_v2(text, tables, filename, "JA")
    
    return {"filename": filename, "type": "unknown"}


def parse_pdf_sync(file_bytes: bytes, filename: str) -> dict:
    """Wrapper for thread pool execution."""
    return parse_pdf(file_bytes, filename)


# ============== Audit Logic ==============

def calculate_status(tax_value: Optional[float], fibu_value: Optional[float]) -> tuple:
    """Calculate comparison status and difference."""
    if tax_value is not None and fibu_value is not None:
        diff = round(abs(tax_value - fibu_value), 2)
        status = "MATCH" if diff < 0.01 else "MISMATCH"
        return status, diff
    elif tax_value is None and fibu_value is None:
        return "NO_DATA", 0
    else:
        return "INCOMPLETE", 0


def get_difference_hint(diff: float, rule: str) -> Optional[str]:
    """Generate a helpful hint for mismatches."""
    if diff < 0.01:
        return None
    
    hints = {
        "R805": f"Differenz von CHF {diff:,.2f}. Prüfen Sie auf nicht verbuchte Verzugszinsen oder fehlende Steuerabrechnungen.",
        "R806": f"Differenz von CHF {diff:,.2f}. Prüfen Sie auf ausstehende Rückerstattungen oder Gutschriften.",
    }
    
    return hints.get(rule, f"Differenz von CHF {diff:,.2f} festgestellt.")


def perform_audit_with_breakdown(
    tax_docs: List[dict], 
    fibu_docs: List[dict],
    er_docs: List[dict],
    bilanz_docs: List[dict]
) -> List[AuditResult]:
    """Perform comprehensive audit with all document types."""
    results = []
    
    # Separate tax docs by target account
    tax_items_1012 = []
    tax_items_2002 = []
    
    for doc in tax_docs:
        if doc.get("restanzen_gemeinde") is not None and doc["restanzen_gemeinde"] > 0:
            item = TaxItem(
                year=doc.get("year", "Unknown"),
                amount=doc["restanzen_gemeinde"],
                source=doc["filename"],
                label=f"Total Restanzen ({doc.get('type', 'Tax')})",
                doc_type=doc.get("type", "Tax")
            )
            
            if doc.get("is_negative"):
                tax_items_2002.append(item)
            else:
                tax_items_1012.append(item)
    
    # Rule R805: Steuerforderungen (1012.00)
    fibu_items_r805 = []
    
    for doc in fibu_docs:
        if doc.get("account") == "1012.00" and doc.get("saldo") is not None:
            fibu_items_r805.append(FibuItem(
                account="1012.00",
                amount=doc["saldo"],
                source=doc["filename"],
                label="Kontoauszug Saldo"
            ))
    
    if not fibu_items_r805:
        for doc in bilanz_docs:
            if doc.get("account_1012") is not None:
                fibu_items_r805.append(FibuItem(
                    account="1012.xx",
                    amount=doc["account_1012"],
                    source=doc["filename"],
                    label="Bilanz Bestand"
                ))
    
    tax_total = sum(item.amount for item in tax_items_1012) if tax_items_1012 else None
    fibu_total = sum(item.amount for item in fibu_items_r805) if fibu_items_r805 else None
    
    status, diff = calculate_status(tax_total, fibu_total)
    
    results.append(AuditResult(
        summary=AuditSummary(
            rule="R805",
            description="Steuerforderungen (Konto 1012.00) vs. Steuerabrechnungen (positive Restanzen)",
            status=status,
            difference=diff,
            tax_total=round(tax_total, 2) if tax_total else None,
            fibu_total=round(fibu_total, 2) if fibu_total else None,
            hint=get_difference_hint(diff, "R805") if status == "MISMATCH" else None
        ),
        details=AuditDetails(tax_items=tax_items_1012, fibu_items=fibu_items_r805)
    ))
    
    # Rule R806: Steuerverpflichtungen (2002.00)
    fibu_items_r806 = []
    
    for doc in fibu_docs:
        if doc.get("account") == "2002.00" and doc.get("saldo") is not None:
            fibu_items_r806.append(FibuItem(
                account="2002.00",
                amount=doc["saldo"],
                source=doc["filename"],
                label="Kontoauszug Saldo"
            ))
    
    if not fibu_items_r806:
        for doc in bilanz_docs:
            if doc.get("account_2002") is not None:
                fibu_items_r806.append(FibuItem(
                    account="2002.xx",
                    amount=doc["account_2002"],
                    source=doc["filename"],
                    label="Bilanz Bestand"
                ))
    
    tax_total = sum(item.amount for item in tax_items_2002) if tax_items_2002 else None
    fibu_total = sum(item.amount for item in fibu_items_r806) if fibu_items_r806 else None
    
    status, diff = calculate_status(tax_total, fibu_total)
    
    results.append(AuditResult(
        summary=AuditSummary(
            rule="R806",
            description="Steuerverpflichtungen (Konto 2002.00) vs. Steuerabrechnungen (negative Restanzen)",
            status=status,
            difference=diff,
            tax_total=round(tax_total, 2) if tax_total else None,
            fibu_total=round(fibu_total, 2) if fibu_total else None,
            hint=get_difference_hint(diff, "R806") if status == "MISMATCH" else None
        ),
        details=AuditDetails(tax_items=tax_items_2002, fibu_items=fibu_items_r806)
    ))
    
    return results


# ============== API Endpoints ==============

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Revipro Reconciliation Engine", "version": "5.0.0", "ai_enabled": True}


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_files(
    files: List[UploadFile] = File(...),
    user_context: Optional[str] = None
):
    """Analyze uploaded PDF files with AI-powered insights."""
    start_time = time.time()
    
    print(f"\n{'='*60}")
    print(f"Received request to analyze {len(files)} files.")
    if user_context:
        print(f"User context: {user_context[:200]}...")
    
    tax_docs = []
    fibu_docs = []
    er_docs = []
    bilanz_docs = []
    
    # Generate session ID early for file storage
    session_id = str(uuid.uuid4())
    
    # Log analysis start (disabled - causing crashes)
    # await log_activity(
    #     session_id=session_id,
    #     event_type="analysis_start",
    #     event_category="document",
    #     data={"file_count": len(files), "has_context": bool(user_context)}
    # )
    file_storage[session_id] = []
    
    loop = asyncio.get_event_loop()
    
    for file in files:
        try:
            print(f"\nProcessing: {file.filename}")
            if not file.filename.lower().endswith('.pdf'):
                print(f"  Skipping non-PDF file")
                continue
            
            file_bytes = await file.read()
            print(f"  Read {len(file_bytes)} bytes")
            
            # Store for potential reprocessing
            file_storage[session_id].append((file.filename, file_bytes))
            
            try:
                # Increase timeout for large PDFs (up to 60s per file)
                parsed = await asyncio.wait_for(
                    loop.run_in_executor(executor, parse_pdf_sync, file_bytes, file.filename),
                    timeout=60.0
                )
                
                doc_type = parsed.get("type", "unknown")
                print(f"  Result type: {doc_type}")
                
                if doc_type == "quellensteuer":
                    print(f"    Skipping Quellensteuer document")
                    continue
                elif doc_type in ["JA", "SR", "NAST"]:
                    print(f"    Year: {parsed.get('year')}, Restanzen: {parsed.get('restanzen_gemeinde')}, Negative: {parsed.get('is_negative')}")
                    tax_docs.append(parsed)
                elif doc_type == "fibu":
                    print(f"    Account: {parsed.get('account')}, Saldo: {parsed.get('saldo')}")
                    fibu_docs.append(parsed)
                elif doc_type == "fibu_combined":
                    # Handle combined FiBu documents (multiple accounts in one file)
                    combined_docs = parsed.get("documents", [])
                    print(f"    Combined FiBu: {len(combined_docs)} accounts found")
                    for doc in combined_docs:
                        print(f"      - {doc.get('account')}: {doc.get('saldo')}")
                        fibu_docs.append(doc)
                elif doc_type == "erfolgsrechnung":
                    er_docs.append(parsed)
                elif doc_type == "bilanz":
                    bilanz_docs.append(parsed)
                    
            except asyncio.TimeoutError:
                print(f"  TIMEOUT - skipping file")
                continue
                
        except Exception as e:
            print(f"  ERROR: {str(e)}")
            continue
    
    print(f"\n{'='*60}")
    print(f"Summary: Tax={len(tax_docs)}, FiBu={len(fibu_docs)}, ER={len(er_docs)}, Bilanz={len(bilanz_docs)}")
    
    # Perform audit
    # Auto-detect organization name FIRST
    auto_name = detect_organization_name(tax_docs, fibu_docs)
    print(f"Detected organization: {auto_name}")
    
    try:
        audit_results = perform_audit_with_breakdown(tax_docs, fibu_docs, er_docs, bilanz_docs)
        print("\nAudit completed successfully.")
        for result in audit_results:
            print(f"  {result.summary.rule}: {result.summary.status} (Tax={result.summary.tax_total}, FiBu={result.summary.fibu_total})")
    except Exception as e:
        print(f"Audit ERROR: {str(e)}")
        audit_results = []
    
    # AI Analysis
    ai_insight = None
    if audit_results:
        try:
            print("\nRunning AI analysis...")
            ai_insight = await analyze_with_claude(
                [result.model_dump() for result in audit_results],
                tax_docs,
                fibu_docs,
                user_context
            )
            print(f"AI analysis complete: {ai_insight.summary[:100]}...")
        except Exception as e:
            print(f"AI analysis error: {e}")
    
    # Create a chat session for this audit (session_id already generated above)
    chat_sessions[session_id] = {
        "messages": [],
        "audit_context": {
            "client_name": auto_name,
            "files_processed": len(files),
            "tax_files": len(tax_docs),
            "fibu_files": len(fibu_docs),
            "results": [r.model_dump() for r in audit_results]
        },
        "created_at": datetime.now()
    }
    
    print(f"Created chat session: {session_id}")
    
    # Calculate duration
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Log analysis complete (disabled for now - causing crashes)
    # await log_activity(
    #     session_id=session_id,
    #     event_type="analysis_complete",
    #     event_category="document",
    #     data={
    #         "files_processed": len(files),
    #         "tax_files": len(tax_docs),
    #         "fibu_files": len(fibu_docs),
    #         "organization": auto_name,
    #         "audit_results_count": len(audit_results),
    #         "matches": len([r for r in audit_results if r.summary.status == "MATCH"]),
    #         "mismatches": len([r for r in audit_results if r.summary.status == "MISMATCH"]),
    #     },
    #     duration_ms=duration_ms,
    #     status="success"
    # )
    
    # Save to Supabase in background
    def save_to_supabase_background():
        try:
            # Save session
            session_data = {
                "id": session_id, 
                "status": "active",
                "organization_type": auto_name
            }
            supabase.table("sessions").upsert(session_data).execute()
            print(f"Session saved to Supabase: {session_id} ({auto_name})")
            
            # Save documents to Supabase (metadata only - PDFs stay in storage)
            for filename, file_bytes in file_storage.get(session_id, []):
                try:
                    doc_data = {
                        "session_id": session_id,
                        "filename": filename,
                        "file_path": f"{session_id}/{filename}",
                        "file_size": len(file_bytes),
                        "document_type": "pdf"
                    }
                    supabase.table("documents").insert(doc_data).execute()
                except Exception as e:
                    print(f"Document save error: {e}")
        except Exception as e:
            print(f"Supabase save error (non-critical): {e}")
    
    threading.Thread(target=save_to_supabase_background, daemon=True).start()
    
    # Detect learning opportunities (DISABLED - causing crashes)
    # if auto_name and auto_name != "Steuerprüfung":
    #     learning_suggestions = await detect_learning_opportunities(
    #         session_id, auto_name, tax_docs, fibu_docs, 
    #         [r.model_dump() for r in audit_results]
    #     )
    #     if learning_suggestions:
    #         await save_learning_suggestions(session_id, auto_name, learning_suggestions)
    
    return AnalysisResponse(
        results=audit_results,
        files_processed=len(files),
        tax_files=len(tax_docs),
        fibu_files=len(fibu_docs),
        annual_report_files=len(er_docs) + len(bilanz_docs),
        ai_insight=ai_insight,
        session_id=session_id
    )


# ============== Chat Endpoint ==============

@app.post("/chat", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest):
    """
    Interactive chat with Claude AI about the audit results.
    Claude can ask clarifying questions and the user can provide context.
    """
    start_time = time.time()
    session_id = request.session_id
    
    # Log chat message received (disabled)
    # await log_activity(
    #     session_id=session_id,
    #     event_type="chat_message_received",
    #     event_category="chat",
    #     data={
    #         "message_length": len(request.message),
    #         "model": request.model,
    #         "has_audit_context": request.include_audit_context
    #     }
    # )
    
    # Get or create session
    if session_id not in chat_sessions:
        chat_sessions[session_id] = {
            "messages": [],
            "audit_context": {},
            "created_at": datetime.now()
        }
    
    session = chat_sessions[session_id]
    
    # Add user message to history
    session["messages"].append({
        "role": "user",
        "content": request.message
    })
    
    # Get client knowledge if available
    client_name = session.get("audit_context", {}).get("client_name")
    client_knowledge = {}
    if client_name:
        client_knowledge = await get_client_knowledge(client_name)
    
    # Build system prompt with complete Swiss tax knowledge
    system_prompt = """Du bist ein Experte für Schweizer Gemeindesteuerprüfung und Finanzbuchhaltung.

## DEIN FACHWISSEN: Steuerabgleich Schweizer Gemeinden

### Dokumenttypen:
1. **JA (Jahresabrechnung)**: Steuerabrechnung des aktuellen Jahres
   - Zeile 45 "Total Restanzen" = SOLL-Buchung im aktuellen Jahr
   - Nur EIN Betrag pro Jahr (kein Vorjahr zum Auflösen)

2. **SR (Steuerrestanzen)**: Abrechnungen aus Vorjahren (2023, 2022, 2021, etc.)
   - Zeile 45 "Total Restanzenvortrag" = HABEN-Buchung (Auflösung Vorjahr)
   - Zeile 51 "Total Restanzen" = SOLL-Buchung (neuer Stand)
   - Je älter, desto kleiner werden die Beträge (bis CHF 0.00)

3. **NAST (Nachsteuern)**: Nachträgliche Steuerforderungen
   - Zeile 38 "Total Restanzenvortrag inkl. Zinsen"

### Kontenlogik:
- **Konto 1012.00** (Aktiven): POSITIVE Restanzen (Steuerforderungen)
- **Konto 2002.00** (Passiven): NEGATIVE Restanzen (Steuerverpflichtungen/Überzahlungen)
  - Auf der Passivseite werden negative Werte POSITIV dargestellt!

### Spaltenlogik (wichtig!):
- Bei Gemeinden: Spalte "Politische Gemeinde" oder "Gemeinde"
- Bei Kirchen: Spalte "ref. Kirche" oder "kath. Kirche"
- Bei Schulen: Spalte "Sekundarschule" oder entsprechend

### Abstimmungslogik:
Der FiBu-Endsaldo muss = Summe aller aktuellen Restanzen sein:
- Konto 1012.00 Endsaldo = Summe(alle positiven Restanzen aus JA + SR + NAST)
- Konto 2002.00 Endsaldo = Summe(alle negativen Restanzen, als positiver Wert)

### Typische Differenz-Ursachen:
1. Nicht alle SR-Dokumente hochgeladen (häufigster Fehler!)
2. Verzugszinsen nicht verbucht
3. Falsche Spalte ausgelesen (z.B. Kanton statt Gemeinde)
4. Startsaldo statt Endsaldo gelesen
5. Doppelbuchungen oder fehlende Umbuchungen

### Kombinierte FiBu-Dokumente:
Manche Gemeinden haben 1012.00 und 2002.00 in EINEM PDF.
- Achte auf "Endsaldo" (nicht Startsaldo!)
- Wenn Endsaldo leer oder 0: Konto wurde aufgelöst

## DEINE AUFGABEN:
1. Erkläre Prüfungsergebnisse verständlich
2. Frage nach fehlenden Dokumenten
3. Hilf bei der Interpretation von Differenzen
4. Passe dich an verschiedene Organisationen an (Gemeinden, Kirchen, Schulen)
5. Gib konkrete Handlungsempfehlungen

## KOMMUNIKATION:
- Antworte IMMER auf Deutsch
- Sei präzise bei Zahlen und Konten
- Frage zurück wenn unklar: "Welche Spalte enthält die Gemeindewerte?"
- Erkläre Fachbegriffe wenn nötig

## FORMAT-REGELN (WICHTIG!):
- KEINE Markdown-Headers wie # ## ### verwenden!
- Schreibe natürlichen Fliesstext mit Absätzen
- Für Listen verwende • oder - am Zeilenanfang
- Für Betonungen schreibe GROSSBUCHSTABEN oder *Sternchen*
- Zahlen immer als CHF X'XXX.XX formatieren
- Halte Antworten kurz und prägnant (max 3-4 Absätze)
- Schreibe wie in einem Chat, nicht wie in einem Dokument

## LEARNING-FUNKTION:
Wenn der Benutzer sagt "Merke dir..." oder "Speichere...", dann:
1. Antworte mit: "Verstanden! Ich habe [X] gespeichert und werde dies bei der nächsten Prüfung berücksichtigen."
2. Verwende die Funktion save_knowledge im Chat

**Beispiele:**
- Benutzer: "Merke dir: Bei Lufingen ist die Spalte Politische Gemeinde relevant"
  → Du: "Verstanden! Ich habe gespeichert: Spalte 'Politische Gemeinde' für Gemeinde Lufingen."

- Benutzer: "Die Differenz von CHF 50 ist normal, das sind immer Verzugszinsen"
  → Du: "Verstanden! Ich habe als bekanntes Muster gespeichert: CHF 50 Differenz = Verzugszinsen."

- Benutzer: "Bei dieser Kirche nutzen wir nur Konto 1012.10, nicht 1012.00"
  → Du: "Verstanden! Gespeichert: Konto 1012.10 für diese Kirche."

**Wichtig:** Bestätige IMMER was du gelernt hast!

"""
    
    # Add client-specific knowledge if available
    if client_knowledge:
        system_prompt += f"""
## CLIENT-SPEZIFISCHES WISSEN: {client_name}

Diese Informationen wurden aus früheren Prüfungen gelernt und vom Benutzer bestätigt:

"""
        if client_knowledge.get("column_preferences"):
            system_prompt += "**Spalten-Präferenzen:**\n"
            for pref in client_knowledge["column_preferences"]:
                system_prompt += f"• {pref.get('column_name', 'Unbekannt')}\n"
            system_prompt += "\n"
        
        if client_knowledge.get("typical_accounts"):
            system_prompt += "**Typische Konten:**\n"
            for acc in client_knowledge["typical_accounts"]:
                system_prompt += f"• {acc.get('accounts', [])}\n"
            system_prompt += "\n"
        
        if client_knowledge.get("known_anomalies"):
            system_prompt += "**Bekannte Besonderheiten:**\n"
            for anom in client_knowledge["known_anomalies"]:
                system_prompt += f"• {anom.get('description', 'Keine Beschreibung')}\n"
            system_prompt += "\n"
    
    # Add audit context if available
    audit_context = session.get("audit_context", {})
    if audit_context and request.include_audit_context:
        system_prompt += f"""
## Aktuelle Prüfungsdaten:

**Verarbeitete Dokumente:** {audit_context.get('files_processed', 0)}
- Steuerabrechnungen: {audit_context.get('tax_files', 0)}
- FiBu-Kontoauszüge: {audit_context.get('fibu_files', 0)}

**Prüfungsergebnisse:**
"""
        for result in audit_context.get('results', []):
            summary = result.get('summary', {})
            system_prompt += f"""
- {summary.get('rule', 'Regel')}: {summary.get('status', '?')}
  - Steuerabrechnung: CHF {summary.get('tax_total', 'N/A')}
  - FiBu: CHF {summary.get('fibu_total', 'N/A')}
  - Differenz: CHF {summary.get('difference', 0)}
"""

    try:
        # Determine model based on user selection
        # Using Claude 4.5 models (correct API names)
        model_name = "claude-opus-4-5" if request.model == "opus" else "claude-sonnet-4-5"
        max_tokens = 2000 if request.model == "opus" else 1500
        
        print(f"Using model: {model_name}")
        
        # Call Claude with conversation history
        response = anthropic_client.messages.create(
            model=model_name,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=session["messages"]
        )
        
        assistant_message = response.content[0].text
        
        # Detect if user wants to save knowledge
        user_message_lower = request.message.lower()
        knowledge_saved = False
        
        if any(keyword in user_message_lower for keyword in ["merke dir", "speichere", "speicher", "lerne", "für nächstes mal"]):
            # User wants to save something - extract knowledge
            try:
                # Detect what to save
                client_name = session.get("audit_context", {}).get("client_name", "Unbekannt")
                
                # Column preference
                if "spalte" in user_message_lower:
                    column_match = re.search(r"spalte\s+[\"']?([^\"'\n]+)[\"']?", request.message, re.IGNORECASE)
                    if column_match:
                        column_name = column_match.group(1).strip()
                        knowledge_data = {
                            "session_id": session_id,
                            "client_name": client_name,
                            "knowledge_type": "column_preference",
                            "key": "preferred_column",
                            "value": {"column_name": column_name},
                            "description": f"Spalte '{column_name}' bevorzugen"
                        }
                        # Save via endpoint (internal call)
                        def save_bg():
                            try:
                                supabase.table("client_knowledge").upsert({
                                    "client_name": client_name,
                                    "knowledge_type": "column_preference",
                                    "key": "preferred_column",
                                    "value": {"column_name": column_name},
                                    "learned_from_session_id": session_id,
                                    "confirmed_by_user": True,
                                    "confidence": 1.0
                                }, on_conflict="client_name,knowledge_type,key").execute()
                                print(f"✓ Saved column preference: {column_name}")
                            except Exception as e:
                                print(f"Error saving knowledge: {e}")
                        threading.Thread(target=save_bg, daemon=True).start()
                        knowledge_saved = True
                
                # Anomaly/difference pattern
                elif "differenz" in user_message_lower or "abweichung" in user_message_lower:
                    amount_match = re.search(r"chf\s*([\d']+(?:\.\d{2})?)", user_message_lower)
                    if amount_match:
                        amount_str = amount_match.group(1).replace("'", "")
                        def save_bg():
                            try:
                                supabase.table("client_knowledge").upsert({
                                    "client_name": client_name,
                                    "knowledge_type": "anomaly",
                                    "key": f"typical_difference_{amount_str}",
                                    "value": {
                                        "amount": float(amount_str),
                                        "description": request.message,
                                        "is_normal": True
                                    },
                                    "learned_from_session_id": session_id,
                                    "confirmed_by_user": True,
                                    "confidence": 1.0
                                }, on_conflict="client_name,knowledge_type,key").execute()
                                print(f"✓ Saved anomaly pattern: CHF {amount_str}")
                            except Exception as e:
                                print(f"Error saving anomaly: {e}")
                        threading.Thread(target=save_bg, daemon=True).start()
                        knowledge_saved = True
                
                # Custom rule (fallback for anything else)
                else:
                    def save_bg():
                        try:
                            supabase.table("client_knowledge").upsert({
                                "client_name": client_name,
                                "knowledge_type": "custom",
                                "key": f"custom_{datetime.now().timestamp()}",
                                "value": {"note": request.message},
                                "learned_from_session_id": session_id,
                                "confirmed_by_user": True,
                                "confidence": 0.8
                            }).execute()
                            print(f"✓ Saved custom rule")
                        except Exception as e:
                            print(f"Error saving custom rule: {e}")
                    threading.Thread(target=save_bg, daemon=True).start()
                    knowledge_saved = True
                    
            except Exception as e:
                print(f"Knowledge extraction error: {e}")
        
        # If knowledge was saved, add confirmation to assistant message
        if knowledge_saved and "verstanden" not in assistant_message.lower():
            assistant_message = f"✓ Gespeichert!\n\n{assistant_message}"
        
        # Add assistant response to history
        session["messages"].append({
            "role": "assistant",
            "content": assistant_message
        })
        
        # Save to Supabase in background (fire-and-forget)
        def save_chat_background():
            try:
                supabase.table("chat_messages").insert({"session_id": session_id, "role": "user", "content": request.message}).execute()
                supabase.table("chat_messages").insert({"session_id": session_id, "role": "assistant", "content": assistant_message}).execute()
            except Exception as e:
                print(f"Chat save error: {e}")
        threading.Thread(target=save_chat_background, daemon=True).start()
        
        # Log AI response (disabled)
        # duration_ms = int((time.time() - start_time) * 1000)
        # await log_activity(
        #     session_id=session_id,
        #     event_type="chat_response_sent",
        #     event_category="ai",
        #     data={
        #         "model_used": model_name,
        #         "response_length": len(assistant_message),
        #         "knowledge_saved": knowledge_saved
        #     },
        #     duration_ms=duration_ms,
        #     status="success"
        # )
        
        # Generate quick reply suggestions based on context
        suggestions = []
        if "differenz" in assistant_message.lower() or "abweichung" in assistant_message.lower():
            suggestions = [
                "Woher kommt diese Differenz?",
                "Zeige mir die Details",
                "Was soll ich prüfen?"
            ]
        elif "dokument" in assistant_message.lower() or "datei" in assistant_message.lower():
            suggestions = [
                "Das Dokument enthält beide Konten",
                "Der Saldo steht in der letzten Spalte",
                "Es ist ein Kirchensteuer-Dokument"
            ]
        elif "?" in assistant_message:
            suggestions = [
                "Ja, das ist korrekt",
                "Nein, lass mich erklären",
                "Ich bin nicht sicher"
            ]
        else:
            suggestions = [
                "Erkläre das genauer",
                "Was sind die nächsten Schritte?",
                "Gibt es Probleme?"
            ]
        
        return ChatResponse(
            response=assistant_message,
            session_id=session_id,
            suggestions=suggestions
        )
        
    except Exception as e:
        print(f"Chat error: {e}")
        return ChatResponse(
            response=f"Entschuldigung, es gab einen Fehler: {str(e)[:100]}. Bitte versuchen Sie es erneut.",
            session_id=session_id,
            suggestions=["Nochmal versuchen", "Andere Frage stellen"]
        )


@app.post("/chat/context")
async def update_chat_context(session_id: str, audit_results: dict):
    """Update the chat session with audit results for context."""
    if session_id not in chat_sessions:
        chat_sessions[session_id] = {
            "messages": [],
            "audit_context": {},
            "created_at": datetime.now()
        }
    
    chat_sessions[session_id]["audit_context"] = audit_results
    return {"status": "ok", "session_id": session_id}


@app.get("/sessions")
async def list_sessions():
    """Get all sessions from Supabase with message preview."""
    try:
        result = supabase.table("sessions").select("*").order("created_at", desc=True).limit(50).execute()
        sessions = []
        for session in result.data:
            # Get document count for each session
            docs = supabase.table("documents").select("id", count="exact").eq("session_id", session["id"]).execute()
            doc_count = docs.count or 0
            
            # Get message count and preview
            messages = supabase.table("chat_messages").select("content", count="exact").eq("session_id", session["id"]).order("created_at", desc=False).limit(1).execute()
            message_count = messages.count or 0
            first_message = messages.data[0]["content"][:50] + "..." if messages.data else None
            
            sessions.append({
                "id": session["id"],
                "created_at": session["created_at"],
                "updated_at": session.get("updated_at"),
                "status": session.get("status", "active"),
                "organization_type": session.get("organization_type"),
                "document_count": doc_count,
                "message_count": message_count,
                "preview": first_message
            })
        
        return {"sessions": sessions}
    except Exception as e:
        print(f"Error listing sessions: {e}")
        return {"sessions": []}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and all related data."""
    try:
        # Delete from Supabase (cascade will handle related records)
        supabase.table("sessions").delete().eq("id", session_id).execute()
        
        # Also delete from local cache
        if session_id in chat_sessions:
            del chat_sessions[session_id]
        if session_id in file_storage:
            del file_storage[session_id]
        
        return {"status": "ok", "message": "Session deleted"}
    except Exception as e:
        print(f"Error deleting session: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/sessions/new")
async def create_new_session():
    """Create a new empty session."""
    session_id = str(uuid.uuid4())
    
    # Log new session creation (disabled)
    # await log_activity(
    #     session_id=session_id,
    #     event_type="session_created",
    #     event_category="system",
    #     data={}
    # )
    
    # Save to Supabase
    try:
        data = {
            "id": session_id,
            "status": "active",
            "created_at": datetime.now().isoformat()
        }
        supabase.table("sessions").insert(data).execute()
    except Exception as e:
        print(f"Error creating session: {e}")
    
    return {"session_id": session_id, "created_at": datetime.now().isoformat()}


class LogRequest(BaseModel):
    session_id: Optional[str] = None
    event_type: str
    event_category: str
    data: Dict = {}
    user_agent: Optional[str] = None


@app.post("/log")
async def log_frontend_activity(request: LogRequest):
    """Receive and log frontend activities."""
    await log_activity(
        session_id=request.session_id,
        event_type=request.event_type,
        event_category=request.event_category,
        data=request.data,
        user_agent=request.user_agent
    )
    return {"status": "ok"}


@app.get("/analytics")
async def get_analytics(days: int = 7):
    """Get analytics summary for the last N days."""
    try:
        # Get activity summary
        result = supabase.table("analytics_summary").select("*").limit(100).execute()
        
        # Get error summary
        errors = supabase.table("common_errors").select("*").limit(20).execute()
        
        # Get recent sessions count
        sessions_result = supabase.table("sessions").select("id", count="exact").execute()
        
        # Get total documents
        docs_result = supabase.table("documents").select("id", count="exact").execute()
        
        # Calculate stats
        total_activities = sum(row.get("event_count", 0) for row in result.data)
        
        return {
            "summary": {
                "total_sessions": sessions_result.count or 0,
                "total_documents": docs_result.count or 0,
                "total_activities": total_activities,
                "period_days": days
            },
            "activity_by_type": result.data[:20],
            "common_errors": errors.data,
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Analytics error: {e}")
        return {
            "summary": {},
            "activity_by_type": [],
            "common_errors": [],
            "error": str(e)
        }


@app.patch("/sessions/{session_id}/rename")
async def rename_session(session_id: str, organization_type: str = None):
    """Rename a session."""
    try:
        data = {"organization_type": organization_type}
        supabase.table("sessions").update(data).eq("id", session_id).execute()
        return {"status": "ok", "organization_type": organization_type}
    except Exception as e:
        print(f"Error renaming session: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/sessions/{session_id}/suggestions")
async def get_learning_suggestions(session_id: str):
    """Get pending learning suggestions for a session."""
    try:
        result = supabase.table("learning_suggestions").select("*").eq("session_id", session_id).eq("status", "pending").execute()
        return {"suggestions": result.data}
    except Exception as e:
        print(f"Error getting suggestions: {e}")
        return {"suggestions": []}


@app.post("/suggestions/{suggestion_id}/accept")
async def accept_learning_suggestion(suggestion_id: str):
    """Accept a learning suggestion and add it to client knowledge."""
    try:
        # Get the suggestion
        suggestion = supabase.table("learning_suggestions").select("*").eq("id", suggestion_id).execute()
        if not suggestion.data:
            return {"status": "error", "message": "Suggestion not found"}
        
        sug = suggestion.data[0]
        
        # Add to client_knowledge
        knowledge_data = {
            "client_name": sug["client_name"],
            "knowledge_type": sug["suggestion_type"],
            "key": sug["title"],
            "value": sug["proposed_knowledge"],
            "learned_from_session_id": sug["session_id"],
            "confirmed_by_user": True,
            "confidence": 1.0
        }
        
        # Upsert (update if exists, insert if not)
        supabase.table("client_knowledge").upsert(knowledge_data).execute()
        
        # Mark suggestion as accepted
        supabase.table("learning_suggestions").update({"status": "accepted"}).eq("id", suggestion_id).execute()
        
        print(f"Accepted learning suggestion: {sug['title']}")
        return {"status": "ok", "message": "Knowledge saved"}
    except Exception as e:
        print(f"Error accepting suggestion: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/suggestions/{suggestion_id}/reject")
async def reject_learning_suggestion(suggestion_id: str):
    """Reject a learning suggestion."""
    try:
        supabase.table("learning_suggestions").update({"status": "rejected"}).eq("id", suggestion_id).execute()
        return {"status": "ok"}
    except Exception as e:
        print(f"Error rejecting suggestion: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/knowledge/save")
async def save_knowledge_manually(
    session_id: str,
    client_name: str,
    knowledge_type: str,
    key: str,
    value: dict,
    description: str = None
):
    """
    Manually save knowledge from chat.
    Used when user says "Merke dir..." or "Speichere..."
    """
    try:
        knowledge_data = {
            "client_name": client_name,
            "knowledge_type": knowledge_type,
            "key": key,
            "value": value,
            "learned_from_session_id": session_id,
            "confirmed_by_user": True,
            "confidence": 1.0
        }
        
        # Upsert
        result = supabase.table("client_knowledge").upsert(knowledge_data, on_conflict="client_name,knowledge_type,key").execute()
        
        print(f"Manually saved knowledge: {client_name} - {key}")
        return {
            "status": "ok", 
            "message": f"Wissen gespeichert: {key}",
            "knowledge_id": result.data[0]["id"] if result.data else None
        }
    except Exception as e:
        print(f"Error saving knowledge manually: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/reprocess")
async def reprocess_files(request: ReprocessRequest):
    """
    Reprocess previously uploaded files with new parameters.
    Useful when user provides context like "use column Politische Gemeinde".
    """
    session_id = request.session_id
    
    if session_id not in file_storage or not file_storage[session_id]:
        return {"error": "Keine Dateien zum erneuten Verarbeiten gefunden. Bitte laden Sie die Dateien erneut hoch."}
    
    print(f"\n{'='*60}")
    print(f"Reprocessing files for session {session_id}")
    print(f"Column: {request.column_name}, Org: {request.organization_type}")
    
    # Get stored files
    stored_files = file_storage[session_id]
    
    tax_docs = []
    fibu_docs = []
    er_docs = []
    bilanz_docs = []
    
    loop = asyncio.get_event_loop()
    
    for filename, file_bytes in stored_files:
        try:
            print(f"\nReprocessing: {filename}")
            
            # Parse with context (could be enhanced to use column_name)
            parsed = await asyncio.wait_for(
                loop.run_in_executor(executor, parse_pdf_sync, file_bytes, filename),
                timeout=30.0
            )
            
            if parsed:
                doc_type = parsed.get("type", "unknown")
                
                if doc_type == "quellensteuer":
                    continue
                elif doc_type in ["JA", "SR", "NAST"]:
                    tax_docs.append(parsed)
                elif doc_type == "fibu":
                    fibu_docs.append(parsed)
                elif doc_type == "fibu_combined":
                    for doc in parsed.get("documents", []):
                        fibu_docs.append(doc)
                elif doc_type == "erfolgsrechnung":
                    er_docs.append(parsed)
                elif doc_type == "bilanz":
                    bilanz_docs.append(parsed)
                    
        except Exception as e:
            print(f"  Error: {e}")
            continue
    
    # Perform audit
    audit_results = perform_audit_with_breakdown(tax_docs, fibu_docs, er_docs, bilanz_docs)
    
    # Update session context
    if session_id in chat_sessions:
        chat_sessions[session_id]["audit_context"] = {
            "files_processed": len(stored_files),
            "tax_files": len(tax_docs),
            "fibu_files": len(fibu_docs),
            "results": [r.model_dump() for r in audit_results]
        }
    
    return {
        "results": [r.model_dump() for r in audit_results],
        "files_processed": len(stored_files),
        "tax_files": len(tax_docs),
        "fibu_files": len(fibu_docs),
        "message": f"Erneut verarbeitet: {len(tax_docs)} Steuerabrechnungen, {len(fibu_docs)} FiBu-Kontoauszüge"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
