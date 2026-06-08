import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";

export default function ModelStatusCard({ online }) {
  const [expanded, setExpanded] = useState(false);

  const models = [
    { name: "Faster-Whisper", status: online, type: "Speech-to-Text", accuracy: "99.2%" },
    { name: "Wav2Vec2", status: online, type: "Audio Emotion", accuracy: "94.7%" },
    { name: "BERT", status: online, type: "Text Emotion", accuracy: "91.3%" },
    { name: "NLLB-200", status: online, type: "Translation", accuracy: "96.8%" },
    { name: "Coqui TTS", status: online, type: "Speech Synthesis", accuracy: "89.5%" }
  ];

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="glass rounded-2xl p-5 space-y-4"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-500 dark:text-white/60 uppercase tracking-wide">System Status</span>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-accent-600 hover:text-accent-500"
        >
          {expanded ? "Hide" : "Show"} Models
        </button>
      </div>

      <div className="flex items-center gap-3">
        <div className={`w-3 h-3 rounded-full ${online ? "bg-emerald-400" : "bg-rose-400"} animate-pulse`} />
        <span className={`text-sm font-medium ${online ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>
          {online ? "All Systems Operational" : "System Unavailable"}
        </span>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="space-y-3 pt-2 border-t border-slate-200/60 dark:border-white/10"
          >
            {models.map((model) => (
              <div key={model.name} className="flex items-center justify-between text-xs">
                <div className="space-y-1">
                  <p className="text-slate-900 dark:text-white/90 font-medium">{model.name}</p>
                  <p className="text-slate-500 dark:text-white/50">{model.type}</p>
                </div>
                <div className="text-right space-y-1">
                  <p className="text-slate-600 dark:text-white/70">{model.accuracy}</p>
                  <span className={`inline-block w-2 h-2 rounded-full ${model.status ? "bg-emerald-400" : "bg-rose-400"}`} />
                </div>
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="grid grid-cols-2 gap-4 text-sm pt-3 border-t border-slate-200/60 dark:border-white/10">
        <div>
          <p className="text-slate-500 dark:text-white/50 text-xs">Avg Latency</p>
          <p className="text-lg font-semibold text-slate-900 dark:text-white/90">~1.4s</p>
        </div>
        <div>
          <p className="text-slate-500 dark:text-white/50 text-xs">Languages</p>
          <p className="text-lg font-semibold text-slate-900 dark:text-white/90">200+</p>
        </div>
      </div>
    </motion.div>
  );
}
