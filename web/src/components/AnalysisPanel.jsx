import { motion } from "framer-motion";
import EmotionBars from "./EmotionBars";
import JsonViewer from "./JsonViewer";

const EMOTION_COLORS = {
  happy: "bg-emotion-happy",
  sad: "bg-emotion-sad",
  angry: "bg-emotion-angry",
  neutral: "bg-emotion-neutral",
  fearful: "bg-emotion-fearful"
};

export default function AnalysisPanel({ result, segments, emotionScores }) {
  if (!result) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="card-surface p-8 space-y-4 text-center"
      >
        <div className="w-16 h-16 mx-auto rounded-full bg-gradient-to-br from-accent-500/20 to-aura-600/20 flex items-center justify-center">
          <span className="text-3xl">🎙️</span>
        </div>
        <div className="space-y-2">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Ready to Analyze</h3>
          <p className="text-sm text-slate-500 dark:text-white/60 max-w-md mx-auto">
            Upload an audio file to receive comprehensive speech analysis including transcription, 
            emotion detection, dialect classification, multilingual translation, and emotion-preserved speech output.
          </p>
        </div>
        <div className="flex flex-wrap justify-center gap-2 pt-4">
          <span className="badge bg-white/70 dark:bg-white/10 border border-slate-200/70 dark:border-white/10">Speech-to-Text</span>
          <span className="badge bg-white/70 dark:bg-white/10 border border-slate-200/70 dark:border-white/10">Emotion Analysis</span>
          <span className="badge bg-white/70 dark:bg-white/10 border border-slate-200/70 dark:border-white/10">Dialect Detection</span>
          <span className="badge bg-white/70 dark:bg-white/10 border border-slate-200/70 dark:border-white/10">Translation</span>
          <span className="badge bg-white/70 dark:bg-white/10 border border-slate-200/70 dark:border-white/10">Speech Synthesis</span>
        </div>
      </motion.div>
    );
  }

  const emotionColor = EMOTION_COLORS[result.detected_emotion] || "bg-white/20";
  const handleCopyTranslation = async () => {
    if (!result?.translated_text) return;
    await navigator.clipboard.writeText(result.translated_text);
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <section className="card-surface p-6 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white">📝 Transcription</h3>
          <span className="badge bg-white/70 dark:bg-white/10 border border-slate-200/70 dark:border-white/10">{result.detected_language || "auto"}</span>
        </div>
        <p className="text-sm text-slate-700 dark:text-white/80 leading-relaxed">{result.transcript}</p>
        <details className="mt-3">
          <summary className="text-xs text-accent-600 cursor-pointer">View word segments</summary>
          <div className="mt-2 max-h-40 overflow-auto text-xs text-slate-500 dark:text-white/60 space-y-1">
            {segments?.length ? (
              segments.map((seg, idx) => (
                <div key={`${seg.start}-${idx}`} className="flex items-center justify-between">
                  <span>{seg.text}</span>
                  <span>{seg.start.toFixed(2)}s - {seg.end.toFixed(2)}s</span>
                </div>
              ))
            ) : (
              <p>No segments available.</p>
            )}
          </div>
        </details>
      </section>

      <section className="card-surface p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white">😊 Emotion Analysis</h3>
          <span className={`badge ${emotionColor} text-white`}>{result.detected_emotion}</span>
        </div>
        <div className="flex items-center gap-4">
          <div className={`w-12 h-12 rounded-full ${emotionColor} bg-opacity-20 flex items-center justify-center text-2xl`}>
            {result.detected_emotion === "happy" && "😊"}
            {result.detected_emotion === "sad" && "😢"}
            {result.detected_emotion === "angry" && "😠"}
            {result.detected_emotion === "fearful" && "😨"}
            {result.detected_emotion === "neutral" && "😐"}
            {!result.detected_emotion && "🎭"}
          </div>
          <div>
            <p className="text-sm text-slate-700 dark:text-white/80">Confidence: {Math.round((result.confidence || 0) * 100)}%</p>
            <p className="text-xs text-slate-500 dark:text-white/50">Emotion inferred from vocal tone and semantic context.</p>
          </div>
        </div>
        <EmotionBars scores={emotionScores} />
      </section>

      <section className="card-surface p-6 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white">🗺️ Dialect Classification</h3>
          <div className="flex items-center gap-2">
            <span className="badge bg-white/70 dark:bg-white/10 border border-slate-200/70 dark:border-white/10 capitalize">{result.detected_dialect?.replace("_", " ") || "Standard"}</span>
          </div>
        </div>
        <p className="text-xs text-slate-500 dark:text-white/60">
          Linguistic pattern analysis for regional dialect identification. Supports Telugu regional variations.
        </p>
      </section>

      <section className="card-surface p-6 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white">🌍 Translation</h3>
          <span className="badge bg-white/70 dark:bg-white/10 border border-slate-200/70 dark:border-white/10">{result.detected_language} → {result.target_language}</span>
        </div>
        <p className="text-sm text-slate-700 dark:text-white/80 leading-relaxed">{result.translated_text}</p>
        <button
          onClick={handleCopyTranslation}
          className="text-xs px-3 py-2 rounded-full border border-slate-200/70 dark:border-white/10 hover:bg-white/70 dark:hover:bg-white/10 w-fit"
        >
          Copy translation
        </button>
      </section>

      <section className="card-surface p-6 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white">🔊 Speech Output</h3>
          <span className={`badge ${emotionColor} text-white`}>{result.detected_emotion}</span>
        </div>
        <p className="text-xs text-slate-500 dark:text-white/60">
          Synthesized with emotion-based prosody ({result.detected_emotion} emotion affects speech rate)
        </p>
        {result.output_audio_url ? (
          <div className="space-y-3">
            <audio 
              controls 
              src={result.output_audio_url} 
              className="w-full"
              onLoadedMetadata={(e) => {
                console.log("[Audio Debug] Loaded:", {
                  duration: e.target.duration,
                  src: e.target.src
                });
              }}
              onError={(e) => {
                console.error("[Audio Debug] Error:", e.target.error);
              }}
            />
            <a
              className="inline-flex items-center justify-center px-4 py-2 rounded-full bg-white/70 dark:bg-white/10 text-xs hover:bg-white/90 dark:hover:bg-white/20 border border-slate-200/70 dark:border-white/10"
              href={result.output_audio_url}
              download
            >
              Download Audio
            </a>
          </div>
        ) : (
          <p className="text-xs text-slate-500 dark:text-white/60">TTS not available. Audio output not generated.</p>
        )}
      </section>

      <section>
        <JsonViewer data={result} />
      </section>
    </motion.div>
  );
}
