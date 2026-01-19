"""
Revipro Reconciliation Engine - LLM-Only PDF Analysis
Version 6.0 - Pure LLM Vision (No pdfplumber/regex)

The LLM reads PDFs directly and extracts all data.
Chat always has access to original PDFs via signed URLs.
"""
import re
import os
import asyncio
import threading
import base64
import json
import io
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# AI Integration
from anthropic import Anthropic
from supabase import create_client, Client
from google import genai as google_genai

# Initialize Anthropic client
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable is required")
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Initialize Gemini 3 client
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is required")
gemini_client = google_genai.Client(api_key=GEMINI_API_KEY)

# Initialize Supabase client with Service Role Key
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://poeulzxkjcxeszfcsiks.supabase.co")
if SUPABASE_URL:
    SUPABASE_URL = SUPABASE_URL.rstrip("/") + "/"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY environment variable is required")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Session storage for chat history (local cache, backed by Supabase)
import uuid
from datetime import datetime
import time

chat_sessions: Dict[str, Dict] = {}  # session_id -> {messages: [], pdf_urls: [], created_at: datetime}

# Thread pool for async operations
executor = ThreadPoolExecutor(max_workers=4)


# ============== Pydantic Models ==============

class TaxItem(BaseModel):
    year: str
    amount: float
    source: str
    label: str = ""
    doc_type: str = ""


class FibuItem(BaseModel):
    account: str
    amount: float
    source: str
    label: str = ""


class AuditDetails(BaseModel):
    tax_items: List[TaxItem] = []
    fibu_items: List[FibuItem] = []


class AuditSummary(BaseModel):
    rule: str
    description: str
    status: str  # MATCH, MISMATCH, NO_DATA, INCOMPLETE
    difference: float = 0.0
    tax_total: Optional[float] = None
    fibu_total: Optional[float] = None
    hint: Optional[str] = None


class AuditResult(BaseModel):
    summary: AuditSummary
    details: AuditDetails


class AIInsight(BaseModel):
    summary: str
    findings: List[str] = []
    recommendations: List[str] = []
    confidence: str = "medium"


class AnalysisResponse(BaseModel):
    results: List[AuditResult]
    files_processed: int = 0
    tax_files: int = 0
    fibu_files: int = 0
    annual_report_files: int = 0
    ai_insight: Optional[AIInsight] = None
    session_id: Optional[str] = None


class ChatRequest(BaseModel):
    session_id: str
    message: str
    model: str = "sonnet"  # sonnet, opus, gemini-pro, gemini-flash
    include_audit_context: bool = True


class ChatResponse(BaseModel):
    response: str
    session_id: str
    suggestions: List[str] = []


class ReprocessRequest(BaseModel):
    session_id: str
    column_name: Optional[str] = "Politische Gemeinde"
    organization_type: Optional[str] = None


# ============== FastAPI App ==============

app = FastAPI(
    title="Revipro Reconciliation Engine",
    description="LLM-Only PDF Analysis for Swiss Tax Audits",
    version="6.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Supabase Helper Functions ==============

def save_document_to_supabase(
    session_id: str,
    filename: str,
    file_bytes: bytes,
) -> Optional[str]:
    """Save PDF to Supabase Storage and return the storage path."""
    try:
        storage_path = f"{session_id}/{filename}"
        
        # Upload to storage
        supabase.storage.from_("documents").upload(
            storage_path, 
            file_bytes, 
            {"content-type": "application/pdf"}
        )
        
        # Save metadata to documents table
        supabase.table("documents").insert({
            "session_id": session_id,
            "filename": filename,
            "file_path": storage_path,
            "document_type": "pending",
            "extracted_data": {}
        }).execute()
        
        print(f"  Saved to Supabase: {storage_path}")
        return storage_path
    except Exception as e:
        print(f"  Error saving to Supabase: {e}")
        return None


def get_signed_url(storage_path: str, expires_in: int = 3600) -> Optional[str]:
    """Generate a signed URL for a document in Supabase Storage."""
    try:
        result = supabase.storage.from_("documents").create_signed_url(storage_path, expires_in)
        if result and result.get("signedURL"):
            return result["signedURL"]
        return None
    except Exception as e:
        print(f"  Error creating signed URL: {e}")
        return None


async def get_session_documents(session_id: str) -> List[dict]:
    """Get all documents for a session from Supabase."""
    try:
        result = supabase.table("documents").select("*").eq("session_id", session_id).execute()
        return result.data or []
    except Exception as e:
        print(f"Error getting documents: {e}")
        return []


async def get_session_pdf_urls(session_id: str) -> List[dict]:
    """Get signed URLs for all PDFs in a session."""
    documents = await get_session_documents(session_id)
    pdf_urls = []
    
    for doc in documents:
        file_path = doc.get("file_path")
        if file_path:
            url = get_signed_url(file_path)
            if url:
                pdf_urls.append({
                    "filename": doc.get("filename"),
                    "url": url,
                    "file_path": file_path
                })
    
    return pdf_urls


async def get_client_knowledge(client_name: str) -> dict:
    """Get all stored knowledge for a client."""
    try:
        result = supabase.table("client_knowledge").select("*").eq("client_name", client_name).execute()
        knowledge = {
            "column_preferences": [],
            "typical_accounts": [],
            "known_anomalies": []
        }
        for row in result.data or []:
            k_type = row.get("knowledge_type", "")
            if "column" in k_type:
                knowledge["column_preferences"].append(row.get("value", {}))
            elif "account" in k_type:
                knowledge["typical_accounts"].append(row.get("value", {}))
            elif "anomal" in k_type or "pattern" in k_type:
                knowledge["known_anomalies"].append(row.get("value", {}))
        return knowledge
    except Exception as e:
        print(f"Error getting client knowledge: {e}")
        return {}


# ============== LLM Analysis Functions ==============

SWISS_TAX_AUDIT_PROMPT = """Du bist ein Experte für Schweizer Gemeindesteuerprüfung.

## DEINE AUFGABE:
Analysiere die hochgeladenen PDF-Dokumente und extrahiere alle relevanten Steuerdaten.

## DOKUMENTTYPEN DIE DU ERKENNEN MUSST:

### 1. Steuerabrechnungen (JA, SR, NAST)
- **JA (Jahresabrechnung)**: Aktuelle Jahresabrechnung
  - Zeile 45 "Total Restanzen" = Steuerforderungen des aktuellen Jahres
  - Nur bei JA ist Zeile 45 eine SOLL-Buchung
  
- **SR (Steuerrestanzen)**: Abrechnungen aus Vorjahren (2023, 2022, etc.)
  - Zeile 45 "Total Restanzenvortrag" = HABEN-Buchung (Auflösung Vorjahr)
  - Zeile 51 "Total Restanzen" = neuer Stand per Jahresende
  
- **NAST (Nachsteuern)**: Nachträgliche Steuerforderungen
  - Zeile 38 oder 44 "Total Restanzen Nachsteuern"

### 2. FiBu-Kontoauszüge
- **Konto 1012.00**: Steuerforderungen (POSITIVE Restanzen)
- **Konto 2002.00**: Steuerverpflichtungen (NEGATIVE Restanzen, als positive Zahl auf Passivseite)
- Suche nach: "Endsaldo", "Saldo per 31.12.", "Schlusssaldo"
- WICHTIG: Nimm den ENDSALDO, nicht den Startsaldo!

### 3. Spaltenlogik
- Bei Gemeinden: Spalte "Politische Gemeinde" oder "Gemeinde"
- Bei Kirchen: "ref. Kirche" oder "kath. Kirche"
- Bei Schulen: "Sekundarschule"

## PRÜFUNGSREGELN:

**R805 - Steuerforderungen:**
- Summe aller POSITIVEN Restanzen (JA + SR + NAST) = FiBu Konto 1012.00 Endsaldo

**R806 - Steuerverpflichtungen:**
- Summe aller NEGATIVEN Restanzen = FiBu Konto 2002.00 Endsaldo
- Negative Werte in der Steuerabrechnung werden auf der Passivseite POSITIV dargestellt

## AUSGABEFORMAT (JSON):

```json
{
  "organization_name": "Name der Gemeinde/Organisation",
  "documents": [
    {
      "filename": "Dateiname.pdf",
      "type": "JA|SR|NAST|FiBu",
      "year": "2024",
      "data": {
        "restanzen_gemeinde": 123456.78,
        "is_negative": false,
        "account": "1012.00",
        "saldo": 123456.78
      }
    }
  ],
  "r805_result": {
    "tax_total": 123456.78,
    "fibu_total": 123456.78,
    "difference": 0.00,
    "status": "MATCH|MISMATCH|INCOMPLETE|NO_DATA",
    "tax_items": [
      {"year": "2024", "type": "JA", "amount": 100000.00, "source": "Datei.pdf"}
    ],
    "fibu_items": [
      {"account": "1012.00", "amount": 123456.78, "source": "FiBu.pdf"}
    ]
  },
  "r806_result": {
    "tax_total": null,
    "fibu_total": 0.00,
    "difference": 0.00,
    "status": "MATCH",
    "tax_items": [],
    "fibu_items": []
  },
  "findings": [
    "Steuerabrechnung JA 2024 zeigt CHF 67'884.25 auf Zeile 45",
    "FiBu Konto 1012.00 hat Endsaldo CHF 57'311.04"
  ],
  "recommendations": [
    "Prüfen Sie, ob alle SR-Dokumente hochgeladen wurden",
    "Verzugszinsen könnten die Differenz erklären"
  ]
}
```

Analysiere ALLE Seiten in ALLEN PDFs sorgfältig!
"""


async def analyze_pdfs_with_llm(
    session_id: str,
    model: str = "sonnet"
) -> dict:
    """
    Analyze all PDFs in a session using LLM Vision.
    PDFs are sent via signed URLs - the LLM reads them directly.
    """
    print(f"\n{'='*60}")
    print(f"Analyzing PDFs with LLM for session: {session_id}")
    print(f"Model: {model}")
    
    # Get all PDF URLs for this session
    pdf_urls = await get_session_pdf_urls(session_id)
    
    if not pdf_urls:
        print("No PDFs found for session")
        return {
            "organization_name": "Unbekannt",
            "documents": [],
            "r805_result": {"status": "NO_DATA", "tax_total": None, "fibu_total": None, "difference": 0, "tax_items": [], "fibu_items": []},
            "r806_result": {"status": "NO_DATA", "tax_total": None, "fibu_total": None, "difference": 0, "tax_items": [], "fibu_items": []},
            "findings": ["Keine Dokumente gefunden"],
            "recommendations": ["Bitte laden Sie die Steuerdokumente und FiBu-Kontoauszüge hoch"]
        }
    
    print(f"Found {len(pdf_urls)} PDFs to analyze")
    for pdf in pdf_urls:
        print(f"  - {pdf['filename']}")
    
    # Build content array with all PDFs
    content = []
    for pdf in pdf_urls:
        content.append({
            "type": "document",
            "source": {
                "type": "url",
                "url": pdf["url"]
            }
        })
    
    # Add the analysis prompt
    content.append({
        "type": "text",
        "text": SWISS_TAX_AUDIT_PROMPT
    })
    
    try:
        if model in ["gemini-pro", "gemini-flash"]:
            # Use Gemini 3 for large PDFs
            gemini_model = "gemini-3-pro-preview" if model == "gemini-pro" else "gemini-3-flash-preview"
            print(f"Using Gemini: {gemini_model}")
            
            # For Gemini, we need to download and upload PDFs
            gemini_parts = []
            for pdf in pdf_urls:
                # Download from Supabase
                file_bytes = supabase.storage.from_("documents").download(pdf["file_path"])
                if file_bytes:
                    part = google_genai.types.Part.from_bytes(
                        data=file_bytes,
                        mime_type="application/pdf"
                    )
                    gemini_parts.append(part)
            
            gemini_parts.append(SWISS_TAX_AUDIT_PROMPT)
            
            response = gemini_client.models.generate_content(
                model=gemini_model,
                contents=gemini_parts
            )
            
            response_text = getattr(response, "text", "") or ""
            if not response_text and getattr(response, "candidates", None):
                response_text = "".join([
                    part.text for part in response.candidates[0].content.parts
                    if hasattr(part, "text")
                ])
        else:
            # Use Claude Sonnet/Opus
            model_name = "claude-opus-4-5" if model == "opus" else "claude-sonnet-4-5"
            print(f"Using Claude: {model_name}")
            
            response = anthropic_client.messages.create(
                model=model_name,
                max_tokens=4000,
                messages=[{
                    "role": "user",
                    "content": content
                }]
            )
            
            response_text = response.content[0].text
        
        print(f"LLM response received ({len(response_text)} chars)")
        
        # Parse JSON from response
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
        if json_match:
            result = json.loads(json_match.group(1))
        else:
            # Try to find raw JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group(0))
            else:
                print(f"Could not parse JSON from response: {response_text[:200]}")
                result = {
                    "organization_name": "Unbekannt",
                    "documents": [],
                    "r805_result": {"status": "NO_DATA"},
                    "r806_result": {"status": "NO_DATA"},
                    "findings": ["Analyse konnte nicht abgeschlossen werden"],
                    "recommendations": []
                }
        
        print(f"Analysis complete: {result.get('organization_name', 'Unknown')}")
        return result
        
    except Exception as e:
        print(f"LLM Analysis error: {e}")
        return {
            "organization_name": "Fehler",
            "documents": [],
            "r805_result": {"status": "NO_DATA", "tax_total": None, "fibu_total": None, "difference": 0},
            "r806_result": {"status": "NO_DATA", "tax_total": None, "fibu_total": None, "difference": 0},
            "findings": [f"Fehler bei der Analyse: {str(e)[:100]}"],
            "recommendations": ["Bitte versuchen Sie es erneut"]
        }


def build_audit_results(llm_result: dict) -> List[AuditResult]:
    """Convert LLM analysis result to AuditResult objects."""
    results = []
    
    # R805 - Steuerforderungen
    r805 = llm_result.get("r805_result", {})
    tax_items_805 = [
        TaxItem(
            year=item.get("year", "Unknown"),
            amount=item.get("amount", 0),
            source=item.get("source", ""),
            label=f"Total Restanzen ({item.get('type', 'Tax')})",
            doc_type=item.get("type", "Tax")
        )
        for item in r805.get("tax_items", [])
    ]
    fibu_items_805 = [
        FibuItem(
            account=item.get("account", "1012.00"),
            amount=item.get("amount", 0),
            source=item.get("source", ""),
            label="Kontoauszug Saldo"
        )
        for item in r805.get("fibu_items", [])
    ]
    
    results.append(AuditResult(
        summary=AuditSummary(
            rule="R805",
            description="Steuerforderungen (Konto 1012.00) vs. Steuerabrechnungen (positive Restanzen)",
            status=r805.get("status", "NO_DATA"),
            difference=r805.get("difference", 0),
            tax_total=r805.get("tax_total"),
            fibu_total=r805.get("fibu_total"),
            hint=f"Differenz von CHF {r805.get('difference', 0):,.2f}" if r805.get("status") == "MISMATCH" else None
        ),
        details=AuditDetails(tax_items=tax_items_805, fibu_items=fibu_items_805)
    ))
    
    # R806 - Steuerverpflichtungen
    r806 = llm_result.get("r806_result", {})
    tax_items_806 = [
        TaxItem(
            year=item.get("year", "Unknown"),
            amount=item.get("amount", 0),
            source=item.get("source", ""),
            label=f"Total Restanzen ({item.get('type', 'Tax')})",
            doc_type=item.get("type", "Tax")
        )
        for item in r806.get("tax_items", [])
    ]
    fibu_items_806 = [
        FibuItem(
            account=item.get("account", "2002.00"),
            amount=item.get("amount", 0),
            source=item.get("source", ""),
            label="Kontoauszug Saldo"
        )
        for item in r806.get("fibu_items", [])
    ]
    
    results.append(AuditResult(
        summary=AuditSummary(
            rule="R806",
            description="Steuerverpflichtungen (Konto 2002.00) vs. Steuerabrechnungen (negative Restanzen)",
            status=r806.get("status", "NO_DATA"),
            difference=r806.get("difference", 0),
            tax_total=r806.get("tax_total"),
            fibu_total=r806.get("fibu_total"),
            hint=f"Differenz von CHF {r806.get('difference', 0):,.2f}" if r806.get("status") == "MISMATCH" else None
        ),
        details=AuditDetails(tax_items=tax_items_806, fibu_items=fibu_items_806)
    ))
    
    return results


# ============== API Endpoints ==============

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Revipro Reconciliation Engine", "version": "6.0.0", "ai_only": True}


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_files(
    files: List[UploadFile] = File(...),
    user_context: Optional[str] = None,
    model: str = "sonnet"
):
    """
    Analyze uploaded PDF files using LLM Vision.
    
    1. Upload all PDFs to Supabase Storage
    2. Send signed URLs to LLM
    3. LLM reads and analyzes all PDFs
    4. Return structured audit results
    """
    start_time = time.time()
    
    print(f"\n{'='*60}")
    print(f"Received {len(files)} files for analysis")
    
    # Generate session ID
    session_id = str(uuid.uuid4())
    
    # Create session in Supabase first
    try:
        supabase.table("sessions").insert({
            "id": session_id,
            "status": "active"
        }).execute()
    except Exception as e:
        print(f"Session creation error: {e}")
    
    # Upload all PDFs to Supabase
    uploaded_count = 0
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            print(f"  Skipping non-PDF: {file.filename}")
            continue
        
        file_bytes = await file.read()
        print(f"  Uploading: {file.filename} ({len(file_bytes)} bytes)")
        
        result = save_document_to_supabase(session_id, file.filename, file_bytes)
        if result:
            uploaded_count += 1
    
    print(f"Uploaded {uploaded_count} PDFs to Supabase")
    
    if uploaded_count == 0:
        return AnalysisResponse(
            results=[],
            files_processed=0,
            session_id=session_id,
            ai_insight=AIInsight(
                summary="Keine PDF-Dokumente gefunden",
                findings=["Es wurden keine gültigen PDF-Dateien hochgeladen"],
                recommendations=["Bitte laden Sie PDF-Dateien hoch"],
                confidence="low"
            )
        )
    
    # Analyze with LLM
    llm_result = await analyze_pdfs_with_llm(session_id, model)
    
    # Build audit results
    audit_results = build_audit_results(llm_result)
    
    # Count document types from LLM result
    documents = llm_result.get("documents", [])
    tax_count = len([d for d in documents if d.get("type") in ["JA", "SR", "NAST"]])
    fibu_count = len([d for d in documents if d.get("type") == "FiBu"])
    
    # Create AI insight
    ai_insight = AIInsight(
        summary=f"Analyse für {llm_result.get('organization_name', 'Unbekannt')} abgeschlossen",
        findings=llm_result.get("findings", []),
        recommendations=llm_result.get("recommendations", []),
        confidence="high" if documents else "low"
    )
    
    # Store session context
    chat_sessions[session_id] = {
        "messages": [],
        "llm_result": llm_result,
        "organization_name": llm_result.get("organization_name", "Steuerprüfung"),
        "created_at": datetime.now()
    }
    
    # Update session in Supabase
    try:
        supabase.table("sessions").update({
            "organization_type": llm_result.get("organization_name", "Steuerprüfung"),
            "status": "analyzed"
        }).eq("id", session_id).execute()
    except Exception as e:
        print(f"Session update error: {e}")
    
    duration = time.time() - start_time
    print(f"Analysis complete in {duration:.1f}s")
    
    return AnalysisResponse(
        results=audit_results,
        files_processed=uploaded_count,
        tax_files=tax_count,
        fibu_files=fibu_count,
        annual_report_files=0,
        ai_insight=ai_insight,
        session_id=session_id
    )


@app.post("/chat", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest):
    """
    Chat with AI about the audit results.
    The AI always has access to the original PDFs via signed URLs.
    """
    session_id = request.session_id
    
    print(f"\n{'='*60}")
    print(f"Chat request for session: {session_id}")
    print(f"Message: {request.message[:100]}...")
    print(f"Model: {request.model}")
    
    # Get or create session
    if session_id not in chat_sessions:
        chat_sessions[session_id] = {
            "messages": [],
            "llm_result": {},
            "created_at": datetime.now()
        }
    
    session = chat_sessions[session_id]
    
    # Add user message to history
    session["messages"].append({
        "role": "user",
        "content": request.message
    })
    
    # Get PDF URLs for this session
    pdf_urls = await get_session_pdf_urls(session_id)
    
    # Get client knowledge if available
    org_name = session.get("organization_name", "")
    client_knowledge = await get_client_knowledge(org_name) if org_name else {}
    
    # Build system prompt
    system_prompt = """Du bist ein Experte für Schweizer Gemeindesteuerprüfung.

Du hast Zugriff auf die hochgeladenen PDF-Dokumente und kannst sie jederzeit lesen.

## DEIN FACHWISSEN:

### Dokumenttypen:
- **JA (Jahresabrechnung)**: Zeile 45 "Total Restanzen" = SOLL-Buchung
- **SR (Steuerrestanzen)**: Zeile 45 = HABEN (Auflösung), Zeile 51 = SOLL (neuer Stand)
- **NAST (Nachsteuern)**: Zeile 38/44 "Total Restanzen"

### Kontenlogik:
- **Konto 1012.00**: POSITIVE Restanzen (Steuerforderungen)
- **Konto 2002.00**: NEGATIVE Restanzen (als positiver Wert auf Passivseite)

### Spalten:
- Gemeinden: "Politische Gemeinde"
- Kirchen: "ref. Kirche" oder "kath. Kirche"
- Schulen: "Sekundarschule"

## KOMMUNIKATION:
- Antworte IMMER auf Deutsch
- KEINE Markdown-Headers (##, ###)
- Schreibe natürlichen Fliesstext
- Für Listen: • oder - am Zeilenanfang
- Zahlen: CHF X'XXX.XX
- Kurz und prägnant (max 3-4 Absätze)

## WICHTIG:
Wenn der Benutzer fragt "lies nochmal" oder "prüfe nochmals", dann LESE die PDFs erneut und extrahiere die Daten frisch.
Du hast IMMER Zugriff auf die Original-PDFs!
"""

    # Add client knowledge
    if client_knowledge:
        system_prompt += f"\n\n## CLIENT-WISSEN für {org_name}:\n"
        for pref in client_knowledge.get("column_preferences", []):
            system_prompt += f"• Spalte: {pref.get('column_name', 'Unbekannt')}\n"
    
    # Add previous analysis context
    if session.get("llm_result"):
        llm_result = session["llm_result"]
        system_prompt += f"\n\n## LETZTE ANALYSE:\n"
        system_prompt += f"Organisation: {llm_result.get('organization_name', 'Unbekannt')}\n"
        for finding in llm_result.get("findings", [])[:5]:
            system_prompt += f"• {finding}\n"
    
    try:
        if request.model in ["gemini-pro", "gemini-flash"]:
            # Use Gemini
            gemini_model = "gemini-3-pro-preview" if request.model == "gemini-pro" else "gemini-3-flash-preview"
            
            # Build content with PDFs
            gemini_parts = []
            
            # Add PDFs
            for pdf in pdf_urls[:10]:  # Limit to 10 PDFs
                try:
                    file_bytes = supabase.storage.from_("documents").download(pdf["file_path"])
                    if file_bytes:
                        part = google_genai.types.Part.from_bytes(
                            data=file_bytes,
                            mime_type="application/pdf"
                        )
                        gemini_parts.append(part)
                except Exception as e:
                    print(f"Error loading PDF for Gemini: {e}")
            
            # Add conversation
            gemini_prompt = system_prompt + "\n\n---\n\nKonversation:\n\n"
            for msg in session["messages"]:
                role = "User" if msg["role"] == "user" else "Assistant"
                gemini_prompt += f"{role}: {msg['content']}\n\n"
            
            gemini_parts.append(gemini_prompt)
            
            response = gemini_client.models.generate_content(
                model=gemini_model,
                contents=gemini_parts
            )
            
            assistant_message = getattr(response, "text", "") or ""
            if not assistant_message and getattr(response, "candidates", None):
                assistant_message = "".join([
                    part.text for part in response.candidates[0].content.parts
                    if hasattr(part, "text")
                ])
        else:
            # Use Claude
            model_name = "claude-opus-4-5" if request.model == "opus" else "claude-sonnet-4-5"
            
            # Build messages with PDFs in the first user message
            messages = []
            
            # First message includes PDFs
            first_content = []
            for pdf in pdf_urls[:10]:  # Limit to 10 PDFs
                first_content.append({
                    "type": "document",
                    "source": {
                        "type": "url",
                        "url": pdf["url"]
                    }
                })
            
            # Add conversation history
            for i, msg in enumerate(session["messages"]):
                if i == 0 and msg["role"] == "user":
                    # First user message includes PDFs
                    first_content.append({
                        "type": "text",
                        "text": msg["content"]
                    })
                    messages.append({
                        "role": "user",
                        "content": first_content
                    })
                else:
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            # If no messages yet, add PDFs with current message
            if not messages:
                first_content.append({
                    "type": "text",
                    "text": request.message
                })
                messages = [{"role": "user", "content": first_content}]
            
            response = anthropic_client.messages.create(
                model=model_name,
                max_tokens=2000,
                system=system_prompt,
                messages=messages
            )
            
            assistant_message = response.content[0].text
        
        # Add assistant message to history
        session["messages"].append({
            "role": "assistant",
            "content": assistant_message
        })
        
        # Save to Supabase in background
        def save_chat():
            try:
                supabase.table("chat_messages").insert({
                    "session_id": session_id,
                    "role": "user",
                    "content": request.message
                }).execute()
                supabase.table("chat_messages").insert({
                    "session_id": session_id,
                    "role": "assistant",
                    "content": assistant_message
                }).execute()
            except Exception as e:
                print(f"Chat save error: {e}")
        
        threading.Thread(target=save_chat, daemon=True).start()
        
        # Generate suggestions
        suggestions = []
        if "differenz" in assistant_message.lower() or "abweichung" in assistant_message.lower():
            suggestions = ["Woher kommt diese Differenz?", "Zeige mir die Details", "Was soll ich prüfen?"]
        elif "?" in assistant_message:
            suggestions = ["Ja, das ist korrekt", "Nein, lass mich erklären", "Lies die PDFs nochmal"]
        else:
            suggestions = ["Erkläre das genauer", "Prüfe die Dokumente nochmal", "Was sind die nächsten Schritte?"]
        
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


# ============== Session Management Endpoints ==============

@app.get("/sessions")
async def list_sessions():
    """Get all sessions from Supabase."""
    try:
        result = supabase.table("sessions").select("*").order("created_at", desc=True).limit(50).execute()
        sessions = []
        for session in result.data or []:
            docs = supabase.table("documents").select("id", count="exact").eq("session_id", session["id"]).execute()
            sessions.append({
                "id": session["id"],
                "created_at": session["created_at"],
                "status": session.get("status", "active"),
                "organization_type": session.get("organization_type"),
                "document_count": docs.count or 0
            })
        return {"sessions": sessions}
    except Exception as e:
        print(f"Error listing sessions: {e}")
        return {"sessions": []}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and all related data."""
    try:
        supabase.table("sessions").delete().eq("id", session_id).execute()
        if session_id in chat_sessions:
            del chat_sessions[session_id]
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/sessions/new")
async def create_new_session():
    """Create a new empty session."""
    session_id = str(uuid.uuid4())
    try:
        supabase.table("sessions").insert({
            "id": session_id,
            "status": "active"
        }).execute()
    except Exception as e:
        print(f"Error creating session: {e}")
    return {"session_id": session_id}


@app.patch("/sessions/{session_id}/rename")
async def rename_session(session_id: str, organization_type: str = None):
    """Rename a session."""
    try:
        supabase.table("sessions").update({"organization_type": organization_type}).eq("id", session_id).execute()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============== Logging Endpoint ==============

class LogRequest(BaseModel):
    session_id: Optional[str] = None
    event_type: str
    event_category: str
    data: Dict = {}


@app.post("/log")
async def log_activity(request: LogRequest):
    """Log frontend activity."""
    try:
        supabase.table("activity_logs").insert({
            "session_id": request.session_id,
            "event_type": request.event_type,
            "event_category": request.event_category,
            "data": request.data
        }).execute()
    except Exception as e:
        print(f"Log error: {e}")
    return {"status": "ok"}


# ============== Reprocess Endpoint ==============

@app.post("/reprocess")
async def reprocess_files(request: ReprocessRequest):
    """Reprocess files with new context."""
    session_id = request.session_id
    
    # Re-run LLM analysis with context
    enhanced_prompt = SWISS_TAX_AUDIT_PROMPT
    if request.column_name:
        enhanced_prompt += f"\n\nWICHTIG: Verwende die Spalte '{request.column_name}' für die Datenextraktion!"
    if request.organization_type:
        enhanced_prompt += f"\n\nOrganisation: {request.organization_type}"
    
    llm_result = await analyze_pdfs_with_llm(session_id, "sonnet")
    audit_results = build_audit_results(llm_result)
    
    # Update session
    if session_id in chat_sessions:
        chat_sessions[session_id]["llm_result"] = llm_result
    
    return {
        "results": [r.model_dump() for r in audit_results],
        "session_id": session_id
    }
