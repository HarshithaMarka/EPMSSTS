import { useCallback, useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import AudioInputCard from "./components/AudioInputCard";
import LiveRecorder from "./components/LiveRecorder";
import AnalysisPanel from "./components/AnalysisPanel";
import Stepper from "./components/Stepper";
import ModelStatusCard from "./components/ModelStatusCard";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

const DEFAULT_METADATA = {
  duration: "--",
  format: "--",
  sampleRate: "--"
};

const LANGUAGE_MAP = {
  en: "English",
  es: "Spanish",
  fr: "French",
  de: "German",
  it: "Italian",
  pt: "Portuguese",
  ru: "Russian",
  ja: "Japanese",
  zh: "Chinese",
  ar: "Arabic",
  hi: "Hindi",
  te: "Telugu",
  ta: "Tamil",
  kn: "Kannada",
  ml: "Malayalam"
};

const SUPPORTED_TRANSLATION_LANGUAGE_OPTIONS = [
  { code: "en", label: "🇬🇧 English" },
  { code: "hi", label: "🇮🇳 Hindi" },
  { code: "te", label: "🇮🇳 Telugu" }
];

const SUPPORTED_TRANSLATION_CODES = new Set(
  SUPPORTED_TRANSLATION_LANGUAGE_OPTIONS.map((item) => item.code)
);

const normalizeLanguageCode = (value) => {
  if (!value || typeof value !== "string") return "en";
  const normalized = value.toLowerCase().split("-")[0];
  return SUPPORTED_TRANSLATION_CODES.has(normalized) ? normalized : "en";
};

const NAV_ITEMS = [
  { id: "landing", label: "Home", icon: "✨" },
  { id: "dashboard", label: "Dashboard", icon: "📊" },
  { id: "live", label: "Live Studio", icon: "🎙️" },
  { id: "history", label: "History", icon: "🗂️" },
  { id: "analytics", label: "Analytics", icon: "📈" },
  { id: "settings", label: "Settings", icon: "⚙️" }
];

const PAGE_SUBTITLES = {
  landing: "Project overview and quick start",
  dashboard: "Operational view of usage, health, and performance",
  live: "Real-time translation studio with emotion preservation",
  history: "Recent sessions and replayable outcomes",
  analytics: "Usage intelligence and model performance",
  settings: "Workflow defaults and platform preferences"
};

const PIPELINE_STEPS = [
  "Speech Recognition",
  "Emotion Analysis",
  "Dialect Detection",
  "Translation",
  "Speech Synthesis"
];

const TIMELINE_STEPS = [
  "Listening",
  "Transcribing",
  "Emotion Detection",
  "Dialect Detection",
  "Translation",
  "Speaking"
];

const METRICS = [
  { label: "Sessions", value: "1,284", delta: "+12%", icon: "⚡" },
  { label: "Avg Latency", value: "1.42s", delta: "-0.18s", icon: "⏱️" },
  { label: "Accuracy", value: "96.8%", delta: "+1.1%", icon: "🎯" },
  { label: "Active Languages", value: "42", delta: "+5", icon: "🌍" }
];

const SESSION_HISTORY = [
  { id: "S-2041", language: "English → Telugu", emotion: "Calm", status: "Completed", time: "2m ago" },
  { id: "S-2040", language: "Hindi → English", emotion: "Happy", status: "Completed", time: "10m ago" },
  { id: "S-2039", language: "Telugu → English", emotion: "Neutral", status: "Completed", time: "1h ago" },
  { id: "S-2038", language: "English → Spanish", emotion: "Focused", status: "Completed", time: "3h ago" }
];

const LANGUAGE_USAGE = [
  { label: "English", value: 40, color: "#22d3ee" },
  { label: "Telugu", value: 22, color: "#10b981" },
  { label: "Hindi", value: 18, color: "#f59e0b" },
  { label: "Spanish", value: 12, color: "#38bdf8" },
  { label: "French", value: 8, color: "#e879f9" }
];

const EMOTION_DIST = [
  { label: "Happy", value: 32, color: "#22c55e" },
  { label: "Neutral", value: 28, color: "#94a3b8" },
  { label: "Focused", value: 18, color: "#38bdf8" },
  { label: "Sad", value: 12, color: "#3b82f6" },
  { label: "Angry", value: 10, color: "#ef4444" }
];

const LATENCY_TREND = [1.8, 1.6, 1.7, 1.5, 1.4, 1.3, 1.5];

function StatCard({ icon, label, value, delta }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="card-surface p-5 space-y-3"
    >
      <div className="flex items-center justify-between">
        <span className="text-2xl">{icon}</span>
        <span className="text-xs px-2 py-1 rounded-full bg-white/70 dark:bg-white/10 border border-slate-200/70 dark:border-white/10 text-slate-600 dark:text-white/70">
          {delta}
        </span>
      </div>
      <div>
        <p className="text-xs text-slate-500 dark:text-white/50 uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-semibold text-slate-900 dark:text-white">{value}</p>
      </div>
    </motion.div>
  );
}

function MiniBarChart({ data }) {
  const max = Math.max(...data);
  return (
    <div className="flex items-end gap-2 h-24">
      {data.map((value, idx) => (
        <div
          key={`${value}-${idx}`}
          className="flex-1 rounded-full bg-gradient-to-t from-accent-600 to-aura-500/70"
          style={{ height: `${(value / max) * 100}%` }}
        />
      ))}
    </div>
  );
}

function DonutChart({ data }) {
  const total = data.reduce((sum, item) => sum + item.value, 0);
  let current = 0;
  const stops = data
    .map((item) => {
      const start = (current / total) * 100;
      current += item.value;
      const end = (current / total) * 100;
      return `${item.color} ${start}% ${end}%`;
    })
    .join(", ");

  return (
    <div className="flex items-center gap-6">
      <div
        className="w-28 h-28 rounded-full"
        style={{
          background: `conic-gradient(${stops})`
        }}
      />
      <div className="space-y-2">
        {data.map((item) => (
          <div key={item.label} className="flex items-center gap-2 text-xs">
            <span className="w-2 h-2 rounded-full" style={{ background: item.color }} />
            <span className="text-slate-600 dark:text-white/70">{item.label}</span>
            <span className="text-slate-900 dark:text-white font-semibold">{item.value}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SectionHeader({ title, subtitle }) {
  return (
    <div className="flex items-start justify-between">
      <div>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500 dark:text-white/50">{subtitle}</p>}
      </div>
    </div>
  );
}

export default function App() {
  const [theme, setTheme] = useState("dark");
  const [activePage, setActivePage] = useState("dashboard");
  const [online, setOnline] = useState(false);
  const [inputMode, setInputMode] = useState("upload");
  const [file, setFile] = useState(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [buffer, setBuffer] = useState(null);
  const [metadata, setMetadata] = useState(DEFAULT_METADATA);
  const [targetLang, setTargetLang] = useState("en");
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [segments, setSegments] = useState([]);
  const [emotionScores, setEmotionScores] = useState({});
  const [result, setResult] = useState(null);

  useEffect(() => {
    const stored = localStorage.getItem("epmssts-theme");
    const selectedTheme = stored || "dark";
    setTheme(selectedTheme);
    document.documentElement.dataset.theme = selectedTheme;
    document.documentElement.classList.toggle("dark", selectedTheme === "dark");
  }, []);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`, {
          method: "GET",
          headers: { "Content-Type": "application/json" },
          mode: "cors"
        });

        if (res.ok) {
          setOnline(true);
        } else {
          setOnline(false);
        }
      } catch (healthError) {
        console.error("Health check failed:", healthError.message);
        setOnline(false);
      }
    };

    checkHealth();
    const timer = setInterval(checkHealth, 5000);
    return () => clearInterval(timer);
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("epmssts-theme", next);
    document.documentElement.dataset.theme = next;
    document.documentElement.classList.toggle("dark", next === "dark");
  };

  const decodeAudio = useCallback(async (audioFile) => {
    try {
      const arrayBuffer = await audioFile.arrayBuffer();
      const context = new AudioContext();
      const audioBuffer = await context.decodeAudioData(arrayBuffer.slice(0));
      setBuffer(audioBuffer);
      setMetadata({
        duration: audioBuffer.duration.toFixed(2),
        format: audioFile.type.split("/")[1]?.toUpperCase() || "Audio",
        sampleRate: audioBuffer.sampleRate
      });
    } catch (audioError) {
      console.warn("Audio decode failed; continuing without waveform metadata.", audioError);
      setBuffer(null);
      setMetadata({
        duration: "--",
        format: audioFile.type.split("/")[1]?.toUpperCase() || "Audio",
        sampleRate: "--"
      });
    }
  }, []);

  const handleFileSelect = async (audioFile) => {
    setFile(audioFile);
    setError("");
    setResult(null);
    setSegments([]);
    setEmotionScores({});
    const url = URL.createObjectURL(audioFile);
    setAudioUrl(url);
    await decodeAudio(audioFile);
  };

  const convertToWav = async (audioFile) => {
    try {
      const arrayBuffer = await audioFile.arrayBuffer();
      const audioContext = new AudioContext();
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);

      const numberOfChannels = audioBuffer.numberOfChannels;
      const length = audioBuffer.length * numberOfChannels * 2;
      const bufferData = new ArrayBuffer(44 + length);
      const view = new DataView(bufferData);

      const writeString = (offset, string) => {
        for (let i = 0; i < string.length; i++) {
          view.setUint8(offset + i, string.charCodeAt(i));
        }
      };

      writeString(0, "RIFF");
      view.setUint32(4, 36 + length, true);
      writeString(8, "WAVE");
      writeString(12, "fmt ");
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true);
      view.setUint16(22, numberOfChannels, true);
      view.setUint32(24, audioBuffer.sampleRate, true);
      view.setUint32(28, audioBuffer.sampleRate * numberOfChannels * 2, true);
      view.setUint16(32, numberOfChannels * 2, true);
      view.setUint16(34, 16, true);
      writeString(36, "data");
      view.setUint32(40, length, true);

      const offset = 44;
      const channelData = [];
      for (let i = 0; i < numberOfChannels; i++) {
        channelData.push(audioBuffer.getChannelData(i));
      }

      let pos = 0;
      for (let i = 0; i < audioBuffer.length; i++) {
        for (let channel = 0; channel < numberOfChannels; channel++) {
          const sample = Math.max(-1, Math.min(1, channelData[channel][i]));
          view.setInt16(offset + pos, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
          pos += 2;
        }
      }

      return new Blob([bufferData], { type: "audio/wav" });
    } catch (convertError) {
      console.error("Error converting audio:", convertError);
      throw convertError;
    }
  };

  const handleAnalyze = async () => {
    if (!file) return;

    setLoading(true);
    setError("");
    setResult(null);
    setSegments([]);
    setEmotionScores({});
    setCurrentStep(0);

    try {
      let audioFile = file;
      if (file.type === "audio/webm" || file.name.endsWith(".webm")) {
        try {
          const wavBlob = await convertToWav(file);
          audioFile = new File([wavBlob], file.name.replace(".webm", ".wav"), { type: "audio/wav" });
        } catch (convertError) {
          setError("Live audio conversion failed. Please try again or upload a WAV/MP3 file.");
          setLoading(false);
          return;
        }
      } else if (!file.type || !file.type.startsWith("audio/")) {
        audioFile = new File([file], file.name, { type: "audio/wav" });
      }

      const sttData = new FormData();
      sttData.append("file", audioFile);

      const sttRes = await fetch(`${API_BASE}/stt/transcribe`, {
        method: "POST",
        body: sttData
      });
      if (!sttRes.ok) {
        const errorText = await sttRes.text();
        throw new Error(`Transcription failed: ${errorText}`);
      }
      const sttJson = await sttRes.json();
      setSegments(sttJson.segments || []);
      setCurrentStep(1);

      const emotionData = new FormData();
      emotionData.append("file", audioFile);
      const emotionRes = await fetch(`${API_BASE}/emotion/detect`, {
        method: "POST",
        body: emotionData
      });
      if (!emotionRes.ok) {
        const errorText = await emotionRes.text();
        throw new Error(`Emotion detection failed: ${errorText}`);
      }
      const emotionJson = await emotionRes.json();
      console.log("[EMOTION DEBUG] Detected emotion from backend:", emotionJson.emotion, "Confidence:", emotionJson.confidence);
      setEmotionScores(emotionJson.scores || {});
      setCurrentStep(2);

      const dialectRes = await fetch(`${API_BASE}/dialect/detect?transcript=${encodeURIComponent(sttJson.text)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
      if (!dialectRes.ok) throw new Error("Dialect detection failed.");
      const dialectJson = await dialectRes.json();
      setCurrentStep(3);

      const sourceLang = normalizeLanguageCode(sttJson.language);
      const normalizedTargetLang = normalizeLanguageCode(targetLang);

      const translationRes = await fetch(`${API_BASE}/translate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: sttJson.text,
          source_lang: sourceLang,
          target_lang: normalizedTargetLang
        })
      });
      if (!translationRes.ok) throw new Error("Translation failed.");
      const translationJson = await translationRes.json();
      setCurrentStep(4);

      let outputAudioUrl = "";
      try {
        const ttsPayload = {
          text: translationJson.translated_text,
          language: normalizedTargetLang,
          emotion: emotionJson.emotion
        };
        
        console.log("[EMOTION DEBUG] TTS payload emotion value:", ttsPayload.emotion);
        console.log("[TTS Debug] Starting TTS request:", {
          url: `${API_BASE}/tts/synthesize`,
          textLength: ttsPayload.text.length,
          language: ttsPayload.language,
          emotion: ttsPayload.emotion,
          apiBase: API_BASE
        });
        
        // Create abort controller for timeout (60 seconds for pyttsx3 synthesis)
        const abortController = new AbortController();
        const timeoutId = setTimeout(() => abortController.abort(), 60000);
        
        const ttsRes = await fetch(`${API_BASE}/tts/synthesize`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(ttsPayload),
          signal: abortController.signal
        });
        
        clearTimeout(timeoutId);
        
        console.log("[TTS Debug] Response received:", {
          status: ttsRes.status,
          statusText: ttsRes.statusText,
          contentType: ttsRes.headers.get("content-type"),
          contentLength: ttsRes.headers.get("content-length"),
          url: ttsRes.url,
          ok: ttsRes.ok
        });
        
        if (ttsRes.ok) {
          const blob = await ttsRes.blob();
          console.log("[TTS Debug] Blob received:", {
            size: blob.size,
            type: blob.type,
            firstBytes: blob.size > 0 ? Array.from(new Uint8Array(await blob.slice(0, 12).arrayBuffer())).map(b => b.toString(16).padStart(2, '0')).join(' ') : 'empty'
          });
          
          // Critical diagnostics for the 46-byte issue
          if (blob.size === 46) {
            console.error("[TTS CRITICAL] Got exactly 46 bytes - this is the reported issue!");
            const errorContent = await blob.text();
            console.error("[TTS] 46-byte response content:", errorContent);
          }
          
          if (blob.size > 100) {
            outputAudioUrl = URL.createObjectURL(blob);
            console.log("[TTS Debug] Audio URL created successfully:", {
              url: outputAudioUrl,
              blobSize: blob.size
            });
          } else {
            console.warn("[TTS Debug] Blob too small - capturing content for diagnosis:", {
              size: blob.size,
              type: blob.type
            });
            // Read content to understand what we actually got
            try {
              const content = await blob.text();
              console.warn("[TTS Debug] Response content:", content);
            } catch (e) {
              console.warn("[TTS Debug] Could not read response as text:", e);
            }
          }
        } else {
          const errorBody = await ttsRes.text();
          console.error("[TTS Debug] Server returned error:", {
            status: ttsRes.status,
            statusText: ttsRes.statusText,
            body: errorBody.substring(0, 500)
          });
        }
      } catch (ttsError) {
        if (ttsError.name === 'AbortError') {
          console.error("[TTS Debug] Request timeout after 60 seconds");
        } else {
          console.error("[TTS Debug] Network/fetch error:", {
            message: ttsError.message,
            name: ttsError.name,
            stack: ttsError.stack
          });
        }
      }

      setCurrentStep(5);

      setResult({
        transcript: sttJson.text,
        detected_language: LANGUAGE_MAP[sourceLang] || sourceLang,
        detected_emotion: emotionJson.emotion,
        detected_dialect: dialectJson.dialect,
        translated_text: translationJson.translated_text,
        target_language: LANGUAGE_MAP[normalizedTargetLang] || normalizedTargetLang,
        output_audio_url: outputAudioUrl,
        confidence: emotionJson.confidence
      });
      
      console.log("[Pipeline Debug] Final result:", {
        hasAudio: !!outputAudioUrl,
        audioUrl: outputAudioUrl,
        emotion: emotionJson.emotion,
        translation: translationJson.translated_text
      });
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const statusLabel = useMemo(() => {
    if (!loading) return "Ready";
    return PIPELINE_STEPS[currentStep] || "Processing";
  }, [loading, currentStep]);

  const timelineIndex = loading ? Math.min(currentStep + 1, TIMELINE_STEPS.length - 1) : -1;
  const pageTitle = NAV_ITEMS.find((item) => item.id === activePage)?.label || "Dashboard";

  return (
    <div className="app-shell">
      <div className="app-bg" />
      <div className="relative z-10 flex min-h-screen">
        <aside className="hidden lg:flex flex-col w-72 px-6 py-8 border-r border-slate-200/70 dark:border-white/10 bg-white/70 dark:bg-base-900/70 backdrop-blur">
          <div className="flex items-center gap-3 mb-10">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-accent-500 to-aura-600 flex items-center justify-center text-xl font-bold text-white">
              E
            </div>
            <div>
              <h1 className="text-lg font-semibold text-slate-900 dark:text-white">EPMSSTS</h1>
              <p className="text-xs text-slate-500 dark:text-white/60">Emotion-preserving speech AI</p>
            </div>
          </div>

          <nav className="space-y-2">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.id}
                onClick={() => setActivePage(item.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-2xl text-sm font-medium transition ${
                  activePage === item.id
                    ? "bg-accent-500/15 text-accent-700 dark:text-accent-400 border border-accent-500/30"
                    : "text-slate-600 dark:text-white/70 hover:bg-white/80 dark:hover:bg-white/10"
                }`}
              >
                <span className="text-lg">{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
          </nav>

          <div className="mt-auto space-y-4 pt-6">
            <div className="card-surface p-4">
              <p className="text-xs text-slate-500 dark:text-white/50 uppercase tracking-wide">System Health</p>
              <div className="flex items-center justify-between mt-3">
                <span className="text-sm font-medium text-slate-900 dark:text-white">
                  {online ? "All services online" : "Offline"}
                </span>
                <span className={`w-2 h-2 rounded-full ${online ? "bg-emerald-500" : "bg-rose-500"} animate-pulse`} />
              </div>
              <div className="mt-4 text-xs text-slate-500 dark:text-white/50">
                Next refresh in 5s
              </div>
            </div>
            <button
              onClick={() => setActivePage("live")}
              className="w-full py-3 rounded-2xl bg-gradient-to-r from-accent-600 to-aura-600 text-white text-sm font-semibold shadow-glow"
            >
              Start Live Session
            </button>
          </div>
        </aside>

        <div className="flex-1 flex flex-col">
          <header className="px-6 py-6 flex flex-col gap-4 border-b border-slate-200/70 dark:border-white/10 bg-white/70 dark:bg-base-900/70 backdrop-blur">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-white/50">{pageTitle}</p>
                <h2 className="text-2xl font-semibold text-slate-900 dark:text-white">{pageTitle}</h2>
                <p className="text-xs text-slate-500 dark:text-white/50">{PAGE_SUBTITLES[activePage]}</p>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 text-xs px-3 py-2 rounded-full border border-slate-200/70 dark:border-white/10 bg-white/80 dark:bg-white/5">
                  <span className={`w-2 h-2 rounded-full ${online ? "bg-emerald-500" : "bg-rose-500"} animate-pulse`} />
                  <span className="text-slate-600 dark:text-white/70">{online ? "Operational" : "Offline"}</span>
                </div>
                <button
                  onClick={toggleTheme}
                  className="text-xs px-3 py-2 rounded-full border border-slate-200/70 dark:border-white/10 hover:bg-white/80 dark:hover:bg-white/10"
                >
                  {theme === "dark" ? "Light" : "Dark"} Mode
                </button>
                <button
                  onClick={() => setActivePage("live")}
                  className="text-xs px-4 py-2 rounded-full bg-gradient-to-r from-accent-600 to-aura-600 text-white font-semibold"
                >
                  New Session
                </button>
              </div>
            </div>
          </header>

          <main className="flex-1 px-6 py-8">
            <AnimatePresence mode="wait">
              {activePage === "landing" && (
                <motion.div
                  key="landing"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  className="space-y-8"
                >
                  <section className="grid lg:grid-cols-[1.1fr_0.9fr] gap-6 items-center">
                    <div className="space-y-5">
                      <div className="flex flex-wrap gap-3">
                        <span className="badge-soft">Enterprise Ready</span>
                        <span className="badge-soft">Emotion Fidelity</span>
                        <span className="badge-soft">Real-time</span>
                      </div>
                      <h1 className="text-4xl lg:text-5xl font-display font-semibold text-slate-900 dark:text-white leading-tight">
                        Translate speech with emotion intact in real time.
                      </h1>
                      <p className="text-sm text-slate-600 dark:text-white/70 max-w-xl">
                        EPMSSTS delivers end-to-end speech understanding, dialect awareness, and emotion-preserving
                        translation to keep the speaker intent consistent across languages.
                      </p>
                      <div className="flex flex-wrap gap-4">
                        <button
                          onClick={() => setActivePage("live")}
                          className="px-6 py-3 rounded-2xl bg-gradient-to-r from-accent-600 to-aura-600 text-white text-sm font-semibold shadow-glow"
                        >
                          Start Live Translation
                        </button>
                        <button
                          onClick={() => setActivePage("dashboard")}
                          className="px-6 py-3 rounded-2xl border border-slate-200/70 dark:border-white/10 text-sm font-semibold text-slate-700 dark:text-white"
                        >
                          View Dashboard
                        </button>
                      </div>
                    </div>
                    <div className="card-surface p-6 space-y-4 floaty">
                      <SectionHeader title="Pipeline Preview" subtitle="Live stages with emotion preservation" />
                      <div className="grid gap-3">
                        {TIMELINE_STEPS.map((step, index) => (
                          <div
                            key={step}
                            className="flex items-center justify-between px-4 py-3 rounded-2xl bg-white/70 dark:bg-white/5 border border-slate-200/70 dark:border-white/10"
                          >
                            <span className="text-sm text-slate-700 dark:text-white/80">{step}</span>
                            <span className={`w-2 h-2 rounded-full ${index < 2 ? "bg-emerald-500" : "bg-slate-300 dark:bg-white/20"}`} />
                          </div>
                        ))}
                      </div>
                    </div>
                  </section>

                  <section className="grid lg:grid-cols-3 gap-6">
                    {[
                      {
                        title: "Emotion-aware translation",
                        desc: "Dual-modality emotion fusion to keep intent and tone aligned in every output."
                      },
                      {
                        title: "Live speech studio",
                        desc: "Record, analyze, and play translated speech with real-time waveform telemetry."
                      },
                      {
                        title: "SaaS-ready architecture",
                        desc: "Clear service boundaries, metrics, and deployment-ready separation of concerns."
                      }
                    ].map((feature) => (
                      <div key={feature.title} className="card-surface p-6 space-y-2">
                        <h3 className="text-base font-semibold text-slate-900 dark:text-white">{feature.title}</h3>
                        <p className="text-sm text-slate-600 dark:text-white/70">{feature.desc}</p>
                      </div>
                    ))}
                  </section>
                </motion.div>
              )}

              {activePage === "dashboard" && (
                <motion.div
                  key="dashboard"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  className="space-y-8"
                >
                  <section className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4">
                    {METRICS.map((metric) => (
                      <StatCard key={metric.label} {...metric} />
                    ))}
                  </section>

                  <section className="grid lg:grid-cols-[1.1fr_0.9fr] gap-6">
                    <div className="card-surface p-6 space-y-5">
                      <SectionHeader title="Usage Trend" subtitle="Sessions processed per hour" />
                      <MiniBarChart data={[12, 18, 16, 20, 24, 22, 26, 28]} />
                      <div className="flex items-center justify-between text-xs text-slate-500 dark:text-white/50">
                        <span>00:00</span>
                        <span>24:00</span>
                      </div>
                    </div>
                    <div className="card-surface p-6 space-y-5">
                      <SectionHeader title="Emotion Distribution" subtitle="Last 24 hours" />
                      <DonutChart data={EMOTION_DIST} />
                    </div>
                  </section>

                  <section className="grid lg:grid-cols-[1fr_360px] gap-6">
                    <div className="card-surface p-6 space-y-4">
                      <SectionHeader title="Recent Sessions" subtitle="Most recent translation runs" />
                      <div className="space-y-3">
                        {SESSION_HISTORY.map((session) => (
                          <div
                            key={session.id}
                            className="flex items-center justify-between px-4 py-3 rounded-2xl bg-white/70 dark:bg-white/5 border border-slate-200/70 dark:border-white/10"
                          >
                            <div>
                              <p className="text-sm font-semibold text-slate-900 dark:text-white">{session.id}</p>
                              <p className="text-xs text-slate-500 dark:text-white/50">{session.language}</p>
                            </div>
                            <div className="text-right">
                              <p className="text-xs text-slate-500 dark:text-white/50">{session.time}</p>
                              <p className="text-sm text-slate-700 dark:text-white/80">{session.emotion}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="space-y-6">
                      <ModelStatusCard online={online} />
                      <div className="card-surface p-6 space-y-4">
                        <SectionHeader title="Languages Used" subtitle="Top target languages" />
                        <div className="space-y-3">
                          {LANGUAGE_USAGE.map((lang) => (
                            <div key={lang.label} className="flex items-center gap-3">
                              <span className="text-xs text-slate-600 dark:text-white/70 w-20">{lang.label}</span>
                              <div className="flex-1 h-2 rounded-full bg-slate-200/70 dark:bg-white/10 overflow-hidden">
                                <div
                                  className="h-full"
                                  style={{ width: `${lang.value}%`, background: lang.color }}
                                />
                              </div>
                              <span className="text-xs text-slate-500 dark:text-white/50">{lang.value}%</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </section>
                </motion.div>
              )}

              {activePage === "live" && (
                <motion.div
                  key="live"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  className="space-y-8"
                >
                  <section className="grid lg:grid-cols-[1.2fr_0.8fr] gap-6">
                    <div className="space-y-4">
                      <div className="flex flex-wrap gap-3">
                        <span className="badge-soft">Live Translation</span>
                        <span className="badge-soft">Emotion Fusion</span>
                        <span className="badge-soft">Dialect Aware</span>
                      </div>
                      <h1 className="text-3xl lg:text-4xl font-display font-semibold text-slate-900 dark:text-white">
                        Live Translation Studio
                      </h1>
                      <p className="text-sm text-slate-600 dark:text-white/70 max-w-2xl">
                        Capture live speech or upload audio, then watch each pipeline stage progress with
                        real-time indicators and emotion-preserving synthesis.
                      </p>
                    </div>
                    <div className="card-surface p-6 space-y-4">
                      <SectionHeader title="Session Status" subtitle="Pipeline telemetry" />
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-slate-600 dark:text-white/70">{statusLabel}</span>
                        <span className={`text-xs px-3 py-1 rounded-full ${loading ? "bg-amber-500/20 text-amber-700 dark:text-amber-200" : "bg-emerald-500/15 text-emerald-700 dark:text-emerald-200"}`}>
                          {loading ? "Processing" : "Ready"}
                        </span>
                      </div>
                      <Stepper currentStep={currentStep} steps={PIPELINE_STEPS} />
                    </div>
                  </section>

                  <section className="grid lg:grid-cols-[360px_1fr] gap-6">
                    <div className="space-y-6">
                      <div className="card-surface p-5 space-y-3">
                        <SectionHeader title="Input Mode" subtitle="Switch between upload and live mic" />
                        <div className="flex gap-3">
                          <button
                            onClick={() => setInputMode("upload")}
                            className={`flex-1 px-4 py-2 rounded-2xl text-sm font-medium transition ${
                              inputMode === "upload"
                                ? "bg-accent-500/15 text-accent-700 dark:text-accent-400 border border-accent-500/30"
                                : "bg-white/70 dark:bg-white/5 text-slate-600 dark:text-white/70 border border-slate-200/70 dark:border-white/10"
                            }`}
                          >
                            Upload Audio
                          </button>
                          <button
                            onClick={() => setInputMode("record")}
                            className={`flex-1 px-4 py-2 rounded-2xl text-sm font-medium transition ${
                              inputMode === "record"
                                ? "bg-accent-500/15 text-accent-700 dark:text-accent-400 border border-accent-500/30"
                                : "bg-white/70 dark:bg-white/5 text-slate-600 dark:text-white/70 border border-slate-200/70 dark:border-white/10"
                            }`}
                          >
                            Live Recording
                          </button>
                        </div>
                      </div>

                      <div className="card-surface p-5 space-y-4">
                        <SectionHeader title="Live Indicators" subtitle="Listening and speaking animation" />
                        <div className="flex items-center justify-between">
                          <div className="relative">
                            <div className="w-12 h-12 rounded-full bg-accent-500/20 flex items-center justify-center">
                              <span className="text-lg">🎧</span>
                            </div>
                            {loading && (
                              <div className="absolute inset-0 rounded-full border border-accent-500 pulse-ring" />
                            )}
                          </div>
                          <div className="wave-bars">
                            <span style={{ height: loading ? "26px" : "12px" }} />
                            <span style={{ height: loading ? "20px" : "10px" }} />
                            <span style={{ height: loading ? "30px" : "12px" }} />
                            <span style={{ height: loading ? "18px" : "9px" }} />
                            <span style={{ height: loading ? "26px" : "11px" }} />
                          </div>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-white/50">
                          {loading ? "Processing live input" : "Awaiting audio input"}
                        </p>
                      </div>

                      {error && (
                        <div className="card-surface p-4 border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-100 text-sm">
                          {error}
                          <button onClick={() => setError("")} className="ml-3 text-xs underline">
                            Dismiss
                          </button>
                        </div>
                      )}
                    </div>

                    <div className="space-y-6">
                      <AnimatePresence mode="wait">
                        {inputMode === "upload" ? (
                          <AudioInputCard
                            key="upload"
                            file={file}
                            audioUrl={audioUrl}
                            buffer={buffer}
                            metadata={metadata}
                            onFileSelect={handleFileSelect}
                            onAnalyze={handleAnalyze}
                            isLoading={loading}
                            targetLang={targetLang}
                            setTargetLang={setTargetLang}
                          />
                        ) : (
                          <LiveRecorder
                            key="record"
                            onRecordingComplete={handleFileSelect}
                            isProcessing={loading}
                            targetLang={targetLang}
                            setTargetLang={setTargetLang}
                            onAnalyze={handleAnalyze}
                          />
                        )}
                      </AnimatePresence>

                      <AnalysisPanel result={result} segments={segments} emotionScores={emotionScores} />
                    </div>
                  </section>

                  <section className="card-surface p-6 space-y-4">
                    <SectionHeader title="Live Pipeline Timeline" subtitle="Listening to synthesis transitions" />
                    <div className="grid md:grid-cols-3 xl:grid-cols-6 gap-3">
                      {TIMELINE_STEPS.map((step, index) => {
                        const isActive = index === timelineIndex;
                        const isDone = timelineIndex > index;
                        return (
                          <div
                            key={step}
                            className={`px-4 py-3 rounded-2xl border text-xs font-semibold flex items-center justify-between ${
                              isDone
                                ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-200 border-emerald-500/30"
                                : isActive
                                ? "bg-accent-500/20 text-accent-700 dark:text-accent-200 border-accent-500/30 shimmer"
                                : "bg-white/70 dark:bg-white/5 text-slate-500 dark:text-white/60 border-slate-200/70 dark:border-white/10"
                            }`}
                          >
                            <span>{step}</span>
                            <span className={`w-2 h-2 rounded-full ${isDone ? "bg-emerald-500" : isActive ? "bg-accent-500" : "bg-slate-300 dark:bg-white/20"}`} />
                          </div>
                        );
                      })}
                    </div>
                  </section>
                </motion.div>
              )}

              {activePage === "history" && (
                <motion.div
                  key="history"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  className="space-y-6"
                >
                  <section className="card-surface p-6 space-y-4">
                    <SectionHeader title="Session History" subtitle="Replay and export past sessions" />
                    <div className="space-y-3">
                      {SESSION_HISTORY.map((session) => (
                        <div
                          key={session.id}
                          className="flex flex-wrap items-center justify-between gap-4 px-4 py-4 rounded-2xl bg-white/70 dark:bg-white/5 border border-slate-200/70 dark:border-white/10"
                        >
                          <div>
                            <p className="text-sm font-semibold text-slate-900 dark:text-white">{session.id}</p>
                            <p className="text-xs text-slate-500 dark:text-white/50">{session.language}</p>
                          </div>
                          <div>
                            <p className="text-xs text-slate-500 dark:text-white/50">Emotion</p>
                            <p className="text-sm text-slate-700 dark:text-white/80">{session.emotion}</p>
                          </div>
                          <div>
                            <p className="text-xs text-slate-500 dark:text-white/50">Status</p>
                            <p className="text-sm text-emerald-600 dark:text-emerald-300">{session.status}</p>
                          </div>
                          <div>
                            <p className="text-xs text-slate-500 dark:text-white/50">Time</p>
                            <p className="text-sm text-slate-700 dark:text-white/80">{session.time}</p>
                          </div>
                          <button className="text-xs px-3 py-2 rounded-full border border-slate-200/70 dark:border-white/10 hover:bg-white/80 dark:hover:bg-white/10">
                            View Details
                          </button>
                        </div>
                      ))}
                    </div>
                  </section>
                </motion.div>
              )}

              {activePage === "analytics" && (
                <motion.div
                  key="analytics"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  className="space-y-6"
                >
                  <section className="grid lg:grid-cols-2 gap-6">
                    <div className="card-surface p-6 space-y-4">
                      <SectionHeader title="Latency Trend" subtitle="Average processing latency" />
                      <MiniBarChart data={LATENCY_TREND} />
                      <p className="text-xs text-slate-500 dark:text-white/50">Latency stays under 2s for 92% of sessions.</p>
                    </div>
                    <div className="card-surface p-6 space-y-4">
                      <SectionHeader title="Language Mix" subtitle="Active target languages" />
                      <DonutChart data={LANGUAGE_USAGE} />
                    </div>
                  </section>

                  <section className="card-surface p-6 space-y-4">
                    <SectionHeader title="Model Performance" subtitle="Top signal metrics" />
                    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                      {[
                        { label: "STT Precision", value: "98.9%" },
                        { label: "Emotion F1", value: "92.4%" },
                        { label: "Dialect Accuracy", value: "94.1%" },
                        { label: "TTS MOS", value: "4.6/5" }
                      ].map((metric) => (
                        <div key={metric.label} className="px-4 py-3 rounded-2xl bg-white/70 dark:bg-white/5 border border-slate-200/70 dark:border-white/10">
                          <p className="text-xs text-slate-500 dark:text-white/50">{metric.label}</p>
                          <p className="text-lg font-semibold text-slate-900 dark:text-white">{metric.value}</p>
                        </div>
                      ))}
                    </div>
                  </section>
                </motion.div>
              )}

              {activePage === "settings" && (
                <motion.div
                  key="settings"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  className="space-y-6"
                >
                  <section className="card-surface p-6 space-y-6">
                    <SectionHeader title="Workspace Preferences" subtitle="Set defaults for your sessions" />
                    <div className="grid md:grid-cols-2 gap-4">
                      <label className="text-xs text-slate-500 dark:text-white/60">
                        Default target language
                        <select
                          className="mt-2 w-full bg-white/80 dark:bg-base-700/70 border border-slate-200/70 dark:border-white/10 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
                          value={targetLang}
                          onChange={(event) => setTargetLang(event.target.value)}
                        >
                          {SUPPORTED_TRANSLATION_LANGUAGE_OPTIONS.map(({ code, label }) => (
                            <option key={code} value={code}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="text-xs text-slate-500 dark:text-white/60 p-4 bg-white/70 dark:bg-white/5 rounded-xl border border-slate-200/70 dark:border-white/10">
                        <p className="font-semibold mb-2 text-slate-900 dark:text-white">🤖 Emotion Detection</p>
                        <p>Emotions are automatically detected from audio using Wav2Vec2 and DistilRoBERTa models. No manual selection needed.</p>
                      </div>
                    </div>
                    <div className="grid md:grid-cols-2 gap-4">
                      <label className="text-xs text-slate-500 dark:text-white/60">
                        Auto-play synthesized audio
                        <div className="mt-2 flex items-center gap-3">
                          <input type="checkbox" className="accent-accent-600" defaultChecked />
                          <span className="text-sm text-slate-600 dark:text-white/70">Enable audio auto-play</span>
                        </div>
                      </label>
                      <label className="text-xs text-slate-500 dark:text-white/60">
                        Download output automatically
                        <div className="mt-2 flex items-center gap-3">
                          <input type="checkbox" className="accent-accent-600" />
                          <span className="text-sm text-slate-600 dark:text-white/70">Save output to downloads</span>
                        </div>
                      </label>
                    </div>
                  </section>

                  <section className="card-surface p-6 space-y-4">
                    <SectionHeader title="API & Usage" subtitle="Prepare for billing and access controls" />
                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="px-4 py-3 rounded-2xl bg-white/70 dark:bg-white/5 border border-slate-200/70 dark:border-white/10">
                        <p className="text-xs text-slate-500 dark:text-white/50">API Status</p>
                        <p className="text-sm font-semibold text-slate-900 dark:text-white">Keyless (Dev Mode)</p>
                      </div>
                      <div className="px-4 py-3 rounded-2xl bg-white/70 dark:bg-white/5 border border-slate-200/70 dark:border-white/10">
                        <p className="text-xs text-slate-500 dark:text-white/50">Usage Tier</p>
                        <p className="text-sm font-semibold text-slate-900 dark:text-white">Starter / 5k min</p>
                      </div>
                    </div>
                  </section>
                </motion.div>
              )}
            </AnimatePresence>
          </main>

          <footer className="px-6 py-6 text-xs text-slate-500 dark:text-white/50 border-t border-slate-200/70 dark:border-white/10">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-4">
                <span>EPMSSTS © 2026</span>
                <span className="w-1 h-1 rounded-full bg-slate-300 dark:bg-white/30" />
                <span>Emotion-Preserving Multilingual Speech-to-Speech Translation System</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="badge bg-white/70 dark:bg-white/5 border border-slate-200/70 dark:border-white/10">5 AI Models</span>
                <span className="badge bg-white/70 dark:bg-white/5 border border-slate-200/70 dark:border-white/10">200+ Languages</span>
              </div>
            </div>
          </footer>
        </div>
      </div>
    </div>
  );
}
