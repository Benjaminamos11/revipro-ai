"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Sparkles, Lock } from "lucide-react";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    
    // Hardcoded password for prototype
    if (password === "revipro2026") {
      sessionStorage.setItem("revipro_auth", "true");
      
      // Log successful login
      try {
        await fetch(`${API_URL}/log`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: null,
            event_type: "login_success",
            event_category: "auth",
            data: { timestamp: new Date().toISOString() },
            user_agent: navigator.userAgent,
          }),
        });
      } catch (err) {
        console.error("Logging failed:", err);
      }
      
      router.push("/");
    } else {
      setError("Falsches Passwort");
      setPassword("");
      
      // Log failed login attempt
      try {
        await fetch(`${API_URL}/log`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: null,
            event_type: "login_failed",
            event_category: "auth",
            data: { attempted_password_length: password.length },
            user_agent: navigator.userAgent,
          }),
        });
      } catch (err) {
        console.error("Logging failed:", err);
      }
    }
  };

  return (
    <div className="min-h-screen bg-gradient-mesh flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-48 h-48 mx-auto flex items-center justify-center">
            <img 
              src="https://revipro.ch/wp-content/uploads/2021/02/logo-1-e1613854437795.png" 
              alt="Revipro"
              className="w-full h-full object-contain"
            />
          </div>
        </div>

        {/* Login Form */}
        <div className="glass-card rounded-3xl p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-[rgb(var(--accent-primary))]/10 flex items-center justify-center">
              <Lock className="w-5 h-5 text-[rgb(var(--accent-primary))]" />
            </div>
            <h2 className="text-xl font-semibold text-[rgb(var(--text-primary))]">
              Anmeldung erforderlich
            </h2>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-[rgb(var(--text-secondary))] mb-2">
                Passwort
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Passwort eingeben..."
                autoFocus
                className="w-full px-4 py-3 rounded-xl bg-[rgb(var(--bg-secondary))] border border-[rgb(var(--border-color))] 
                           text-[rgb(var(--text-primary))] placeholder:text-[rgb(var(--text-muted))]
                           focus:outline-none focus:ring-2 focus:ring-[rgb(var(--accent-primary))]/50"
              />
            </div>

            {error && (
              <motion.p
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-sm text-red-500"
              >
                {error}
              </motion.p>
            )}

            <button
              type="submit"
              className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-[rgb(var(--accent-primary))] to-[rgb(var(--accent-secondary))] 
                         text-white font-medium hover:shadow-lg transition-shadow"
            >
              Anmelden
            </button>
          </form>

          <p className="text-center text-xs text-[rgb(var(--text-muted))] mt-6">
            Prototype • Nur für autorisierte Benutzer
          </p>
        </div>

        <p className="text-center text-xs text-[rgb(var(--text-muted))] mt-8">
          100% Swiss Made • Revipro AG
        </p>
      </motion.div>
    </div>
  );
}
