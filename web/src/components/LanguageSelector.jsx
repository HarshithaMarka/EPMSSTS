import { motion } from "framer-motion";
import { useState } from "react";

export default function LanguageSelector({ targetLang, setTargetLang, onAnalyze, disabled, isLoading }) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="card-surface p-6 space-y-4"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Translation Settings</h3>
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-xs text-accent-500 hover:text-accent-400"
        >
          {showAdvanced ? "Hide" : "Show"} Advanced
        </button>
      </div>

      <label className="text-xs text-white/60">
        Target Language
        <select
          className="mt-2 w-full bg-base-700/70 border border-white/10 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
          value={targetLang}
          onChange={(e) => setTargetLang(e.target.value)}
        >
          <option value="en">🇬🇧 English</option>
          <option value="te">🇮🇳 Telugu</option>
          <option value="hi">🇮🇳 Hindi</option>
        </select>
      </label>

      {showAdvanced && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          className="space-y-3 pt-3 border-t border-white/10"
        >
          <p className="text-xs text-white/50">
            Advanced options coming soon: speech rate, pitch adjustment, and voice selection.
          </p>
        </motion.div>
      )}

      <button
        disabled={disabled || isLoading}
        onClick={onAnalyze}
        className="w-full py-3 rounded-xl bg-gradient-to-r from-accent-600 to-aura-600 text-sm font-semibold shadow-glow hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition"
      >
        {isLoading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Processing Pipeline...
          </span>
        ) : (
          "🚀 Start Full Analysis"
        )}
      </button>
    </motion.div>
  );
}
