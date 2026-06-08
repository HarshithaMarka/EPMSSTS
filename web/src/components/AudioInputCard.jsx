import { motion } from "framer-motion";
import Waveform from "./Waveform";

export default function AudioInputCard({
  file,
  audioUrl,
  metadata,
  buffer,
  onFileSelect,
  onAnalyze,
  isLoading,
  targetLang,
  setTargetLang
}) {
  const handleDrop = (event) => {
    event.preventDefault();
    const dropped = event.dataTransfer.files?.[0];
    if (dropped) onFileSelect(dropped);
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      className="card-surface p-6 space-y-5"
      onDragOver={(event) => event.preventDefault()}
      onDrop={handleDrop}
    >
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Audio Input</h2>
        <span className="text-xs text-slate-500 dark:text-white/50">WAV • MP3 • OGG • M4A</span>
      </div>

      <label className="flex flex-col items-center justify-center text-center gap-2 border border-dashed border-slate-200/70 dark:border-white/20 rounded-2xl px-4 py-6 cursor-pointer hover:border-accent-500/60 transition">
        <input
          type="file"
          accept="audio/*"
          className="hidden"
          onChange={(event) => event.target.files?.[0] && onFileSelect(event.target.files[0])}
        />
        <p className="text-sm text-slate-700 dark:text-white/80">Drop audio file here</p>
        <p className="text-xs text-slate-500 dark:text-white/50">or click to browse</p>
      </label>

      {file && (
        <div className="space-y-3">
          <div className="text-sm text-slate-600 dark:text-white/70">
            <strong className="text-slate-900 dark:text-white/90">{file.name}</strong>
            <div className="mt-1 flex flex-wrap gap-3 text-xs">
              <span className="badge bg-white/70 dark:bg-white/10 border border-slate-200/70 dark:border-white/10">{metadata.format}</span>
              <span className="badge bg-white/70 dark:bg-white/10 border border-slate-200/70 dark:border-white/10">{metadata.duration}s</span>
              <span className="badge bg-white/70 dark:bg-white/10 border border-slate-200/70 dark:border-white/10">{metadata.sampleRate} Hz</span>
            </div>
          </div>
          <Waveform buffer={buffer} />
          {audioUrl && (
            <audio controls src={audioUrl} className="w-full" />
          )}
        </div>
      )}

      <div className="space-y-4">
        <label className="text-xs text-slate-500 dark:text-white/60">
          Target language
          <select
            className="mt-2 w-full bg-white/80 dark:bg-base-700/70 border border-slate-200/70 dark:border-white/10 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
            value={targetLang}
            onChange={(event) => setTargetLang(event.target.value)}
          >
            <option value="en">🇬🇧 English</option>
            <option value="hi">🇮🇳 Hindi</option>
            <option value="te">🇮🇳 Telugu</option>
          </select>
        </label>

        <button
          disabled={!file || isLoading}
          onClick={onAnalyze}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-accent-600 to-aura-600 text-sm font-semibold text-white shadow-glow hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition relative overflow-hidden"
        >
          {isLoading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Processing...
            </span>
          ) : (
            "Start Analysis"
          )}
        </button>
      </div>
    </motion.div>
  );
}
