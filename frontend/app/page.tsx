"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useTheme } from "next-themes";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { clsx } from "clsx";
import {
  FileText,
  Upload,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Moon,
  Sun,
  Sparkles,
  X,
  Send,
  Bot,
  User,
  RefreshCw,
  FileUp,
  Plus,
  Trash2,
  Menu,
  Clock,
  ChevronLeft,
} from "lucide-react";

// ============== Types ==============
interface Session {
  id: string;
  created_at: string;
  updated_at?: string;
  status: string;
  organization_type?: string;
  document_count: number;
  message_count?: number;
  preview?: string;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  type?: "text" | "files" | "results" | "action";
  files?: File[];
  results?: AuditResult[];
  action?: {
    type: "upload" | "reprocess";
    label: string;
  };
}

interface AuditResult {
  summary: {
    rule: string;
    description: string;
    status: "MATCH" | "MISMATCH" | "NO_DATA" | "INCOMPLETE" | "INFO";
    difference: number;
    tax_total: number | null;
    fibu_total: number | null;
  };
  details: {
    tax_items: Array<{ year: string; amount: number; source: string }>;
    fibu_items: Array<{ account: string; amount: number; source: string }>;
  };
}

interface AnalysisResponse {
  results: AuditResult[];
  files_processed: number;
  tax_files: number;
  fibu_files: number;
  session_id?: string;
  raw_extractions?: any;
}

interface LearningSuggestion {
  id: string;
  client_name: string;
  suggestion_type: string;
  title: string;
  description: string;
  proposed_knowledge: any;
  status: string;
}

// ============== Theme Toggle ==============
function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return <div className="w-8 h-8" />;

  return (
    <button
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-[rgb(var(--bg-secondary))] transition-colors"
    >
      {resolvedTheme === "dark" ? (
        <Sun className="w-4 h-4 text-[rgb(var(--text-muted))]" />
      ) : (
        <Moon className="w-4 h-4 text-[rgb(var(--text-muted))]" />
      )}
    </button>
  );
}

// ============== Format Currency ==============
function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `CHF ${value.toLocaleString("de-CH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// ============== File Drop Zone (Inline) ==============
function InlineDropZone({ 
  onFilesDropped, 
  disabled 
}: { 
  onFilesDropped: (files: File[]) => void;
  disabled?: boolean;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (disabled) return;
    
    const files = Array.from(e.dataTransfer.files).filter(
      f => f.type === "application/pdf"
    );
    if (files.length > 0) {
      onFilesDropped(files);
    }
  }, [onFilesDropped, disabled]);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (disabled) return;
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      onFilesDropped(files);
    }
  }, [onFilesDropped, disabled]);

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      className={clsx(
        "relative border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all",
        isDragging 
          ? "border-[rgb(var(--accent-primary))] bg-[rgb(var(--accent-primary))]/10" 
          : "border-[rgb(var(--border-color))] hover:border-[rgb(var(--accent-primary))]/50",
        disabled && "opacity-50 cursor-not-allowed"
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        multiple
        onChange={handleChange}
        className="hidden"
        disabled={disabled}
      />
      <div className="flex flex-col items-center gap-3">
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-[rgb(var(--accent-primary))]/20 to-[rgb(var(--accent-secondary))]/20 flex items-center justify-center">
          <FileUp className="w-7 h-7 text-[rgb(var(--accent-primary))]" />
        </div>
        <div>
          <p className="font-medium text-[rgb(var(--text-primary))]">
            PDFs hier ablegen oder klicken
          </p>
          <p className="text-sm text-[rgb(var(--text-muted))] mt-1">
            Steuerabrechnungen, FiBu-Kontoauszüge, Jahresrechnungen
          </p>
        </div>
      </div>
    </div>
  );
}

// ============== Results Display (Compact) ==============
function CompactResults({ results }: { results: AuditResult[] }) {
  return (
    <div className="space-y-3 mt-4">
      {results.map((result, idx) => {
        const s = result.summary;
        const statusColors = {
          MATCH: "text-green-500",
          MISMATCH: "text-amber-500",
          NO_DATA: "text-gray-400",
          INCOMPLETE: "text-blue-400",
          INFO: "text-purple-400",
        };
        const statusIcons = {
          MATCH: <CheckCircle2 className="w-4 h-4" />,
          MISMATCH: <AlertTriangle className="w-4 h-4" />,
          NO_DATA: <span className="text-xs">—</span>,
          INCOMPLETE: <span className="text-xs">⋯</span>,
          INFO: <span className="text-xs">ℹ</span>,
        };

        return (
          <div 
            key={idx} 
            className="p-4 rounded-xl bg-[rgb(var(--bg-secondary))]/50 border border-[rgb(var(--border-color))]/30"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className={clsx("flex items-center", statusColors[s.status])}>
                    {statusIcons[s.status]}
                  </span>
                  <span className="font-medium text-[rgb(var(--text-primary))] text-sm">
                    {s.rule}
                  </span>
                </div>
                <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
                  {s.description}
                </p>
              </div>
              {s.difference > 0 && (
                <span className="text-xs font-mono text-amber-500">
                  Δ {formatCurrency(s.difference)}
                </span>
              )}
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
              <div>
                <span className="text-[rgb(var(--text-muted))]">Steuer:</span>
                <span className="ml-2 font-mono text-[rgb(var(--text-primary))]">
                  {formatCurrency(s.tax_total)}
                </span>
              </div>
              <div>
                <span className="text-[rgb(var(--text-muted))]">FiBu:</span>
                <span className="ml-2 font-mono text-[rgb(var(--text-primary))]">
                  {formatCurrency(s.fibu_total)}
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ============== Chat Message Component ==============
function ChatMessageComponent({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  if (isSystem) {
    return (
      <div className="flex justify-center my-4">
        <span className="text-xs text-[rgb(var(--text-muted))] bg-[rgb(var(--bg-secondary))] px-3 py-1 rounded-full">
          {message.content}
        </span>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={clsx("flex gap-3 mb-4", isUser ? "flex-row-reverse" : "flex-row")}
    >
      {/* Avatar */}
      <div className={clsx(
        "w-9 h-9 rounded-xl flex-shrink-0 flex items-center justify-center",
        isUser 
          ? "bg-[rgb(var(--accent-primary))]" 
          : "bg-gradient-to-br from-[rgb(var(--accent-primary))] to-[rgb(var(--accent-secondary))]"
      )}>
        {isUser ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-white" />}
      </div>

      {/* Message Content */}
      <div className={clsx(
        "max-w-[80%] rounded-2xl",
        isUser 
          ? "bg-[rgb(var(--accent-primary))] text-white p-4 rounded-tr-md" 
          : "bg-[rgb(var(--bg-secondary))] border border-[rgb(var(--border-color))]/30 p-4 rounded-tl-md"
      )}>
        {/* Text content */}
        {message.content && (
          <div className={clsx(
            "text-sm leading-relaxed whitespace-pre-wrap",
            isUser ? "text-white" : "text-[rgb(var(--text-primary))]"
          )}>
            {message.content}
          </div>
        )}

        {/* File list */}
        {message.files && message.files.length > 0 && (
          <div className="mt-3 space-y-1">
            {message.files.map((file, idx) => (
              <div key={idx} className="flex items-center gap-2 text-xs opacity-80">
                <FileText className="w-3 h-3" />
                <span>{file.name}</span>
              </div>
            ))}
          </div>
        )}

        {/* Results */}
        {message.results && message.results.length > 0 && (
          <CompactResults results={message.results} />
        )}
      </div>
    </motion.div>
  );
}

// ============== Learning Suggestions Modal ==============
function LearningSuggestionsModal({ 
  suggestions, 
  onAccept, 
  onReject,
  onClose 
}: {
  suggestions: LearningSuggestion[];
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
  onClose: () => void;
}) {
  if (suggestions.length === 0) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-[rgb(var(--bg-primary))] rounded-3xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col border border-[rgb(var(--border-color))]/30 shadow-2xl"
      >
        {/* Header */}
        <div className="p-6 border-b border-[rgb(var(--border-color))]/30 bg-gradient-to-r from-[rgb(var(--accent-primary))]/10 to-[rgb(var(--accent-secondary))]/10">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-[rgb(var(--accent-primary))] to-[rgb(var(--accent-secondary))] flex items-center justify-center">
                <Sparkles className="w-6 h-6 text-white" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-[rgb(var(--text-primary))]">
                  Neue Erkenntnisse entdeckt
                </h3>
                <p className="text-sm text-[rgb(var(--text-muted))]">
                  Soll ich diese Muster für künftige Prüfungen speichern?
                </p>
              </div>
            </div>
            <button onClick={onClose} className="text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))]">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Suggestions List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {suggestions.map((suggestion) => (
            <div 
              key={suggestion.id}
              className="p-5 rounded-2xl bg-[rgb(var(--bg-secondary))] border border-[rgb(var(--border-color))]/30"
            >
              <h4 className="font-semibold text-[rgb(var(--text-primary))] mb-2 flex items-center gap-2">
                <span className="w-6 h-6 rounded-lg bg-[rgb(var(--accent-primary))]/20 text-[rgb(var(--accent-primary))] flex items-center justify-center text-xs">
                  {suggestion.suggestion_type === 'account_pattern' && '📊'}
                  {suggestion.suggestion_type === 'anomaly' && '⚠️'}
                  {suggestion.suggestion_type === 'column_preference' && '📍'}
                  {suggestion.suggestion_type === 'document_format' && '📄'}
                </span>
                {suggestion.title}
              </h4>
              <p className="text-sm text-[rgb(var(--text-secondary))] mb-4">
                {suggestion.description}
              </p>
              
              <div className="flex gap-2">
                <button
                  onClick={() => onAccept(suggestion.id)}
                  className="flex-1 px-4 py-2 rounded-xl bg-gradient-to-r from-[rgb(var(--accent-primary))] to-[rgb(var(--accent-secondary))] text-white text-sm font-medium hover:shadow-lg transition-shadow"
                >
                  Speichern
                </button>
                <button
                  onClick={() => onReject(suggestion.id)}
                  className="px-4 py-2 rounded-xl bg-[rgb(var(--bg-tertiary))] text-[rgb(var(--text-secondary))] text-sm font-medium hover:bg-[rgb(var(--bg-secondary))] transition-colors"
                >
                  Ignorieren
                </button>
              </div>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}

// ============== Sidebar Component ==============
function Sidebar({ 
  sessions, 
  currentSessionId, 
  onSelectSession, 
  onNewSession,
  onDeleteSession,
  onRenameSession
}: {
  sessions: Session[];
  currentSessionId: string;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
  onRenameSession: (id: string, name: string) => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) return "Heute";
    if (days === 1) return "Gestern";
    if (days < 7) return `vor ${days} Tagen`;
    return date.toLocaleDateString("de-CH");
  };

  return (
    <motion.aside
      initial={false}
      animate={{ width: isExpanded ? 280 : 64 }}
      onMouseEnter={() => setIsExpanded(true)}
      onMouseLeave={() => setIsExpanded(false)}
      className="fixed top-0 left-0 h-full bg-[rgb(var(--bg-secondary))]/95 backdrop-blur-xl border-r border-[rgb(var(--border-color))]/30 z-40 flex flex-col overflow-hidden"
      transition={{ duration: 0.2, ease: "easeInOut" }}
    >
        {/* Header */}
        <div className="p-3 border-b border-[rgb(var(--border-color))]/30 flex-shrink-0">
          <button
            onClick={onNewSession}
            className={clsx(
              "w-full flex items-center gap-2 px-3 py-3 rounded-xl bg-gradient-to-r from-[rgb(var(--accent-primary))] to-[rgb(var(--accent-secondary))] text-white font-medium hover:shadow-lg transition-all",
              isExpanded ? "justify-center" : "justify-center"
            )}
            title="Neue Prüfung"
          >
            <Plus className="w-5 h-5 flex-shrink-0" />
            {isExpanded && <span className="whitespace-nowrap">Neue Prüfung</span>}
          </button>
        </div>

        {/* Sessions List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {sessions.length === 0 ? (
            isExpanded ? (
              <div className="text-center py-8 text-xs text-[rgb(var(--text-muted))]">
                Keine Prüfungen
              </div>
            ) : null
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                className={clsx(
                  "group relative rounded-xl cursor-pointer transition-all",
                  currentSessionId === session.id
                    ? "bg-[rgb(var(--accent-primary))]/10 border border-[rgb(var(--accent-primary))]/30"
                    : "bg-[rgb(var(--bg-tertiary))] hover:bg-[rgb(var(--bg-primary))] border border-transparent",
                  isExpanded ? "p-3" : "p-2"
                )}
                onClick={() => onSelectSession(session.id)}
                title={!isExpanded ? formatDate(session.created_at) : undefined}
              >
                {isExpanded ? (
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Clock className="w-3 h-3 text-[rgb(var(--text-muted))] flex-shrink-0" />
                        <span className="text-xs text-[rgb(var(--text-muted))] truncate">
                          {formatDate(session.created_at)}
                        </span>
                      </div>
                      
                      {editingId === session.id ? (
                        <input
                          type="text"
                          value={editingName}
                          onChange={(e) => setEditingName(e.target.value)}
                          onBlur={() => {
                            if (editingName.trim()) {
                              onRenameSession(session.id, editingName.trim());
                            }
                            setEditingId(null);
                          }}
                          onKeyPress={(e) => {
                            if (e.key === 'Enter') {
                              if (editingName.trim()) {
                                onRenameSession(session.id, editingName.trim());
                              }
                              setEditingId(null);
                            }
                            if (e.key === 'Escape') {
                              setEditingId(null);
                            }
                          }}
                          onClick={(e) => e.stopPropagation()}
                          autoFocus
                          className="w-full text-sm font-medium bg-[rgb(var(--bg-primary))] border border-[rgb(var(--accent-primary))] rounded px-1 py-0.5 text-[rgb(var(--text-primary))] focus:outline-none"
                        />
                      ) : (
                        <p 
                          className="text-sm font-medium text-[rgb(var(--text-primary))] truncate cursor-text"
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingId(session.id);
                            setEditingName(session.organization_type || "Prüfung");
                          }}
                          title="Klicken zum Umbenennen"
                        >
                          {session.organization_type || "Prüfung"}
                        </p>
                      )}
                      
                      {session.preview && (
                        <p className="text-xs text-[rgb(var(--text-muted))] mt-1 truncate opacity-70">
                          {session.preview}
                        </p>
                      )}
                      
                      <div className="flex items-center gap-2 mt-1">
                        {session.document_count > 0 && (
                          <span className="text-xs text-[rgb(var(--text-muted))]">
                            {session.document_count} Dok.
                          </span>
                        )}
                        {session.message_count && session.message_count > 0 && (
                          <span className="text-xs text-[rgb(var(--text-muted))]">
                            • {session.message_count} Chats
                          </span>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm("Möchten Sie diese Prüfung wirklich löschen?")) {
                          onDeleteSession(session.id);
                        }
                      }}
                      className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-red-500/10 rounded flex-shrink-0"
                    >
                      <Trash2 className="w-4 h-4 text-red-500" />
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center justify-center">
                    <FileText className={clsx(
                      "w-5 h-5",
                      currentSessionId === session.id 
                        ? "text-[rgb(var(--accent-primary))]" 
                        : "text-[rgb(var(--text-muted))]"
                    )} />
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-[rgb(var(--border-color))]/30 flex-shrink-0">
          {isExpanded ? (
            <div className="flex items-center gap-2 text-xs text-[rgb(var(--text-muted))]">
              <Sparkles className="w-3 h-3 flex-shrink-0" />
              <span className="truncate">AI-Assistent</span>
            </div>
          ) : (
            <div className="flex justify-center">
              <Sparkles className="w-4 h-4 text-[rgb(var(--text-muted))]" />
            </div>
          )}
        </div>
      </motion.aside>
  );
}

// ============== Constants ==============
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ============== Activity Logging ==============
async function logActivity(
  sessionId: string | null,
  eventType: string,
  eventCategory: string,
  data: any = {}
) {
  try {
    await fetch(`${API_URL}/log`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        event_type: eventType,
        event_category: eventCategory,
        data: data,
        user_agent: navigator.userAgent,
      }),
    });
  } catch (error) {
    // Silent fail - don't disrupt user experience
    console.error("Logging failed:", error);
  }
}

// ============== Main Chat Interface ==============
export default function Home() {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [sessionId, setSessionId] = useState<string>("");
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [showDropZone, setShowDropZone] = useState(true);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisStage, setAnalysisStage] = useState("");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [learningSuggestions, setLearningSuggestions] = useState<LearningSuggestion[]>([]);
  const [selectedModel, setSelectedModel] = useState<"opus" | "sonnet">("opus");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Session Management (define FIRST before useEffects)
  const loadSessions = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/sessions`);
      const data = await response.json();
      setSessions(data.sessions || []);
    } catch (error) {
      console.error("Failed to load sessions:", error);
    }
  }, []);

  const createNewSession = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/sessions/new`, {
        method: "POST",
      });
      const data = await response.json();
      
      setSessionId(data.session_id);
      setMessages([]);
      setUploadedFiles([]);
      setShowDropZone(true);
      
      await loadSessions();
    } catch (error) {
      console.error("Failed to create session:", error);
    }
  }, [loadSessions]);

  const deleteSession = useCallback(async (id: string) => {
    try {
      await fetch(`${API_URL}/sessions/${id}`, {
        method: "DELETE",
      });
      
      if (id === sessionId) {
        createNewSession();
      }
      
      await loadSessions();
    } catch (error) {
      console.error("Failed to delete session:", error);
    }
  }, [sessionId, loadSessions, createNewSession]);

  const selectSession = useCallback(async (id: string) => {
    // TODO: Load session messages and files from Supabase
    setSessionId(id);
    setMessages([]);
    setUploadedFiles([]);
    setShowDropZone(true);
    
    // Load chat history
    try {
      const response = await fetch(`${API_URL}/sessions/${id}/history`);
      if (response.ok) {
        const data = await response.json();
        // Convert to ChatMessage format
        // setMessages(data.messages);
      }
    } catch (error) {
      console.error("Failed to load session:", error);
    }
  }, []);

  const renameSession = useCallback(async (id: string, name: string) => {
    try {
      await fetch(`${API_URL}/sessions/${id}/rename`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ organization_type: name })
      });
      
      // Update local state
      setSessions(prev => prev.map(s => 
        s.id === id ? { ...s, organization_type: name } : s
      ));
    } catch (error) {
      console.error("Failed to rename session:", error);
    }
  }, []);

  const acceptSuggestion = useCallback(async (id: string) => {
    try {
      await fetch(`${API_URL}/suggestions/${id}/accept`, {
        method: "POST",
      });
      
      setLearningSuggestions(prev => prev.filter(s => s.id !== id));
      
      // Add chat message
      const msg: ChatMessage = {
        id: `system-${Date.now()}`,
        role: "system",
        content: "Wissen gespeichert! Ich werde dies bei der nächsten Prüfung berücksichtigen.",
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, msg]);
    } catch (error) {
      console.error("Failed to accept suggestion:", error);
    }
  }, []);

  const rejectSuggestion = useCallback(async (id: string) => {
    try {
      await fetch(`${API_URL}/suggestions/${id}/reject`, {
        method: "POST",
      });
      
      setLearningSuggestions(prev => prev.filter(s => s.id !== id));
    } catch (error) {
      console.error("Failed to reject suggestion:", error);
    }
  }, []);

  // Check authentication
  useEffect(() => {
    const isAuthenticated = sessionStorage.getItem("revipro_auth");
    if (!isAuthenticated) {
      router.push("/login");
    } else {
      loadSessions();
    }
  }, [router, loadSessions]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Initial welcome message - show whenever messages are empty
  useEffect(() => {
    if (messages.length === 0) {
      const welcomeMessage: ChatMessage = {
        id: "welcome",
        role: "assistant",
        content: `Willkommen bei Revipro! Ich bin Ihr Assistent für die Steuerprüfung.

Laden Sie Ihre Dokumente hoch und ich analysiere sie für Sie:
• Steuerabrechnungen (JA, SR, NAST)
• FiBu-Kontoauszüge (1012.00, 2002.00)
• Jahresrechnungen

Ich erkenne automatisch die Dokumenttypen und prüfe die Abstimmung. Falls etwas unklar ist, frage ich nach.`,
        timestamp: new Date(),
        type: "text",
      };
      setMessages([welcomeMessage]);
    }
  }, [messages.length]);

  // Handle file upload
  const handleFilesDropped = useCallback(async (files: File[]) => {
    setUploadedFiles(prev => [...prev, ...files]);
    setShowDropZone(false);
    setIsProcessing(true);
    setAnalysisProgress(0);
    setAnalysisStage("Dokumente werden hochgeladen...");

    // Log file upload
    logActivity(sessionId, "files_uploaded", "ui", {
      file_count: files.length,
      file_names: files.map(f => f.name),
      total_size: files.reduce((sum, f) => sum + f.size, 0)
    });

    // Add user message showing uploaded files
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: `${files.length} Dokument${files.length > 1 ? 'e' : ''} hochgeladen`,
      timestamp: new Date(),
      type: "files",
      files: files,
    };
    setMessages(prev => [...prev, userMsg]);

    // Animate progress
    const progressInterval = setInterval(() => {
      setAnalysisProgress(prev => {
        if (prev < 90) return prev + Math.random() * 15;
        return prev;
      });
    }, 500);

    // Process files
    try {
      setAnalysisStage("PDFs werden analysiert...");
      setAnalysisProgress(20);
      
      const formData = new FormData();
      [...uploadedFiles, ...files].forEach(f => formData.append("files", f));

      // Add timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 min timeout

      const response = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);

      setAnalysisProgress(70);
      setAnalysisStage("Prüfung wird durchgeführt...");

      if (!response.ok) throw new Error("Analyse fehlgeschlagen");

      const data: AnalysisResponse = await response.json();
      
      if (data.session_id) {
        setSessionId(data.session_id);
        
        // Check for learning suggestions after a delay
        setTimeout(async () => {
          try {
            const sugResponse = await fetch(`${API_URL}/sessions/${data.session_id}/suggestions`);
            if (sugResponse.ok) {
              const sugData = await sugResponse.json();
              if (sugData.suggestions && sugData.suggestions.length > 0) {
                setLearningSuggestions(sugData.suggestions);
              }
            }
          } catch (err) {
            console.error("Failed to load suggestions:", err);
          }
        }, 2000);
      }

      // Build response message
      let responseText = `Ich habe ${data.files_processed} Dokumente analysiert:\n`;
      responseText += `• ${data.tax_files} Steuerabrechnung${data.tax_files !== 1 ? 'en' : ''}\n`;
      responseText += `• ${data.fibu_files} FiBu-Kontoauszüg${data.fibu_files !== 1 ? 'e' : ''}\n\n`;

      // Summarize results
      const matches = data.results.filter(r => r.summary.status === "MATCH").length;
      const mismatches = data.results.filter(r => r.summary.status === "MISMATCH").length;
      const incomplete = data.results.filter(r => r.summary.status === "INCOMPLETE").length;

      if (matches > 0) {
        responseText += `✓ ${matches} Prüfung${matches > 1 ? 'en' : ''} bestanden\n`;
      }
      if (mismatches > 0) {
        responseText += `⚠ ${mismatches} Abweichung${mismatches > 1 ? 'en' : ''} gefunden\n`;
      }
      if (incomplete > 0) {
        responseText += `⋯ ${incomplete} Prüfung${incomplete > 1 ? 'en' : ''} unvollständig (Daten fehlen)\n`;
      }

      if (data.tax_files === 0) {
        responseText += `\nHinweis: Es wurden keine Steuerabrechnungen erkannt. Falls Ihre Datei mehrere Abrechnungen enthält (z.B. JA + SR in einem PDF), teilen Sie mir mit, welche Spalte relevant ist (z.B. "Politische Gemeinde").`;
      }

      setAnalysisProgress(100);
      setAnalysisStage("Fertig!");
      clearInterval(progressInterval);

      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: responseText,
        timestamp: new Date(),
        type: "results",
        results: data.results,
      };
      
      // Small delay to show 100% before hiding
      setTimeout(() => {
        setMessages(prev => [...prev, assistantMsg]);
        setIsProcessing(false);
      }, 500);

    } catch (error: any) {
      clearInterval(progressInterval);
      console.error("Analysis error:", error);
      
      // Log error
      logActivity(sessionId, "analysis_error", "error", {
        error_name: error.name,
        error_message: error.message,
        file_count: [...uploadedFiles, ...files].length
      });
      
      let errorContent = "Es gab einen Fehler bei der Analyse.";
      if (error.name === "AbortError") {
        errorContent = "Die Analyse hat zu lange gedauert (Timeout nach 2 Minuten). Bitte versuchen Sie es mit weniger Dokumenten.";
      } else if (error.message && error.message.includes("Failed to fetch")) {
        errorContent = "Verbindung zum Backend fehlgeschlagen. Bitte prüfen Sie Ihre Internetverbindung und versuchen Sie es erneut.";
      } else if (error.message) {
        errorContent = `Fehler: ${error.message}`;
      }
      
      const errorMsg: ChatMessage = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: errorContent,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMsg]);
      setIsProcessing(false);
    }
  }, [uploadedFiles, sessionId]);

  // Send chat message
  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isProcessing) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: content.trim(),
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);
    setInputValue("");
    setIsProcessing(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: content.trim(),
          session_id: sessionId || "default",
          include_audit_context: true,
          model: selectedModel,
        }),
      });

      if (!response.ok) throw new Error("Chat failed");

      const data = await response.json();

      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: data.response,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, assistantMsg]);

    } catch (error) {
      const errorMsg: ChatMessage = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: "Verbindungsfehler. Bitte versuchen Sie es erneut.",
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsProcessing(false);
    }
  }, [sessionId, isProcessing]);

  // Handle key press
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputValue);
    }
  };

  // Quick actions (context-aware)
  const getQuickActions = useCallback(() => {
    const actions = [
      "Merke dir: Spalte 'Politische Gemeinde' verwenden",
      "Speichere: CHF 50.00 Differenz ist normal (Verzugszinsen)",
      "Das ist ein Kirchen-Dokument, nicht Gemeinde",
      "Nochmals analysieren mit neuem Kontext",
      "Erkläre mir die Differenzen",
      "Welche Dokumente fehlen noch?",
    ];
    
    // Filter based on context
    if (messages.some(m => m.type === "results")) {
      return actions;
    }
    
    return [
      "Wie funktioniert die Prüfung?",
      "Was muss ich hochladen?",
      "Kann ich mehrere Gemeinden prüfen?",
    ];
  }, [messages]);

  return (
    <div className="min-h-screen bg-gradient-mesh flex">
      {/* Sidebar */}
      <Sidebar
        sessions={sessions}
        currentSessionId={sessionId}
        onSelectSession={selectSession}
        onNewSession={createNewSession}
        onDeleteSession={deleteSession}
        onRenameSession={renameSession}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 ml-16">
        {/* Header */}
        <header className="sticky top-0 z-20 backdrop-blur-xl bg-[rgb(var(--bg-primary))]/80 border-b border-[rgb(var(--border-color))]/30">
          <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img 
              src="https://revipro.ch/wp-content/uploads/2021/02/logo-1-e1613854437795.png" 
              alt="Revipro"
              className="h-10 w-auto object-contain"
            />
          </div>
          <div className="flex items-center gap-2">
            {uploadedFiles.length > 0 && (
              <span className="text-xs text-[rgb(var(--text-muted))] bg-[rgb(var(--bg-secondary))] px-2 py-1 rounded-full">
                {uploadedFiles.length} Datei{uploadedFiles.length > 1 ? 'en' : ''}
              </span>
            )}
            <ThemeToggle />
          </div>
          </div>
        </header>

        {/* Chat Messages */}
        <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 py-6">
          {/* Messages */}
          {messages.map(msg => (
            <ChatMessageComponent key={msg.id} message={msg} />
          ))}

          {/* Drop Zone (shown initially or when adding more files) */}
          {showDropZone && !isProcessing && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="my-4"
            >
              <InlineDropZone onFilesDropped={handleFilesDropped} disabled={isProcessing} />
            </motion.div>
          )}

          {/* Animated Processing indicator */}
          {isProcessing && (
            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex gap-3 mb-4"
            >
              <div className="w-9 h-9 rounded-xl flex-shrink-0 flex items-center justify-center bg-gradient-to-br from-[rgb(var(--accent-primary))] to-[rgb(var(--accent-secondary))]">
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div className="flex-1 max-w-md bg-[rgb(var(--bg-secondary))] border border-[rgb(var(--border-color))]/30 p-4 rounded-2xl rounded-tl-md">
                <div className="flex items-center gap-2 mb-3">
                  <Loader2 className="w-4 h-4 animate-spin text-[rgb(var(--accent-primary))]" />
                  <span className="text-sm font-medium text-[rgb(var(--text-primary))]">
                    {analysisStage || "Analysiere..."}
                  </span>
                </div>
                
                {/* Progress Bar */}
                <div className="w-full h-2 bg-[rgb(var(--bg-tertiary))] rounded-full overflow-hidden">
                  <motion.div 
                    className="h-full bg-gradient-to-r from-[rgb(var(--accent-primary))] to-[rgb(var(--accent-secondary))]"
                    initial={{ width: "0%" }}
                    animate={{ width: `${analysisProgress}%` }}
                    transition={{ duration: 0.3, ease: "easeOut" }}
                  />
                </div>
                
                <p className="text-xs text-[rgb(var(--text-muted))] mt-2">
                  {analysisProgress < 30 && "PDFs werden gelesen..."}
                  {analysisProgress >= 30 && analysisProgress < 60 && "Daten werden extrahiert..."}
                  {analysisProgress >= 60 && analysisProgress < 90 && "Prüfung wird durchgeführt..."}
                  {analysisProgress >= 90 && "Ergebnisse werden aufbereitet..."}
                </p>
              </div>
            </motion.div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Input Area */}
      <div className="sticky bottom-0 bg-[rgb(var(--bg-primary))]/95 backdrop-blur-xl border-t border-[rgb(var(--border-color))]/30">
        <div className="max-w-4xl mx-auto px-4 py-4">
          {/* Quick Actions */}
          {messages.length > 1 && !isProcessing && (
            <div className="flex flex-wrap gap-2 mb-3">
              <button
                onClick={() => setShowDropZone(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-full bg-[rgb(var(--bg-secondary))] text-[rgb(var(--text-secondary))] hover:bg-[rgb(var(--accent-primary))]/10 hover:text-[rgb(var(--accent-primary))] transition-colors border border-[rgb(var(--border-color))]/30"
              >
                <FileUp className="w-3 h-3" />
                Weitere Dokumente
              </button>
              {getQuickActions().slice(0, 4).map((action, idx) => (
                <button
                  key={idx}
                  onClick={() => sendMessage(action)}
                  className={clsx(
                    "px-3 py-1.5 text-xs rounded-full transition-colors border",
                    action.toLowerCase().startsWith("merke") || action.toLowerCase().startsWith("speichere")
                      ? "bg-[rgb(var(--accent-primary))]/10 text-[rgb(var(--accent-primary))] border-[rgb(var(--accent-primary))]/30 hover:bg-[rgb(var(--accent-primary))]/20"
                      : "bg-[rgb(var(--bg-secondary))] text-[rgb(var(--text-secondary))] border-[rgb(var(--border-color))]/30 hover:bg-[rgb(var(--accent-primary))]/10 hover:text-[rgb(var(--accent-primary))]"
                  )}
                >
                  {action}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <div className="flex gap-3 items-end">
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Nachricht eingeben oder Frage stellen..."
              rows={1}
              disabled={isProcessing}
              className="flex-1 px-4 py-3 rounded-xl bg-[rgb(var(--bg-secondary))] border border-[rgb(var(--border-color))] 
                         text-[rgb(var(--text-primary))] placeholder:text-[rgb(var(--text-muted))]
                         focus:outline-none focus:ring-2 focus:ring-[rgb(var(--accent-primary))]/50 resize-none text-sm
                         disabled:opacity-50"
              style={{ minHeight: "44px", maxHeight: "120px" }}
            />
            <button
              onClick={() => sendMessage(inputValue)}
              disabled={!inputValue.trim() || isProcessing}
              className={clsx(
                "w-11 h-11 rounded-xl flex items-center justify-center transition-all flex-shrink-0",
                inputValue.trim() && !isProcessing
                  ? "bg-gradient-to-r from-[rgb(var(--accent-primary))] to-[rgb(var(--accent-secondary))] text-white shadow-lg"
                  : "bg-[rgb(var(--bg-tertiary))] text-[rgb(var(--text-muted))]"
              )}
            >
              <Send className="w-5 h-5" />
            </button>
          </div>

          {/* Model Toggle */}
          <div className="flex items-center justify-center gap-2 mt-3 mb-2">
            <span className="text-xs text-[rgb(var(--text-muted))]">Modell:</span>
            <div className="flex gap-1 p-1 bg-[rgb(var(--bg-tertiary))] rounded-lg">
              <button
                onClick={() => setSelectedModel("sonnet")}
                className={clsx(
                  "px-3 py-1 text-xs rounded-md transition-all font-medium",
                  selectedModel === "sonnet"
                    ? "bg-gradient-to-r from-[rgb(var(--accent-primary))] to-[rgb(var(--accent-secondary))] text-white shadow-sm"
                    : "text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))]"
                )}
              >
                Sonnet 4.5
              </button>
              <button
                onClick={() => setSelectedModel("opus")}
                className={clsx(
                  "px-3 py-1 text-xs rounded-md transition-all font-medium",
                  selectedModel === "opus"
                    ? "bg-gradient-to-r from-[rgb(var(--accent-primary))] to-[rgb(var(--accent-secondary))] text-white shadow-sm"
                    : "text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))]"
                )}
              >
                Opus 4.5
              </button>
            </div>
          </div>

          <p className="text-center text-xs text-[rgb(var(--text-muted))]">
            100% Swiss Made • Revipro AG
          </p>
        </div>
      </div>
      </div>

      {/* Learning Suggestions Modal */}
      <AnimatePresence>
        {learningSuggestions.length > 0 && (
          <LearningSuggestionsModal
            suggestions={learningSuggestions}
            onAccept={acceptSuggestion}
            onReject={rejectSuggestion}
            onClose={() => setLearningSuggestions([])}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
