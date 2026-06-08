import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

export default function LiveRecorder({
  onRecordingComplete,
  isProcessing,
  targetLang,
  setTargetLang,
  onAnalyze
}) {
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [duration, setDuration] = useState(0);
  const [audioLevel, setAudioLevel] = useState(0);
  const [hasRecording, setHasRecording] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const animationRef = useRef(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
      if (audioContextRef.current) audioContextRef.current.close();
    };
  }, []);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      // Audio analysis setup
      audioContextRef.current = new AudioContext();
      const source = audioContextRef.current.createMediaStreamSource(stream);
      analyserRef.current = audioContextRef.current.createAnalyser();
      analyserRef.current.fftSize = 256;
      source.connect(analyserRef.current);

      const updateAudioLevel = () => {
        if (!analyserRef.current) return;
        const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(dataArray);
        const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
        setAudioLevel(Math.min(average / 128, 1));
        animationRef.current = requestAnimationFrame(updateAudioLevel);
      };
      updateAudioLevel();

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const file = new File([blob], `recording-${Date.now()}.webm`, { type: "audio/webm" });
        onRecordingComplete(file);
        setHasRecording(true);
        
        stream.getTracks().forEach(track => track.stop());
        if (audioContextRef.current) audioContextRef.current.close();
        if (animationRef.current) cancelAnimationFrame(animationRef.current);
      };

      mediaRecorder.start();
      setIsRecording(true);
      setDuration(0);

      timerRef.current = setInterval(() => {
        setDuration(prev => prev + 1);
      }, 1000);

    } catch (error) {
      console.error("Error accessing microphone:", error);
      alert("Unable to access microphone. Please grant permission.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setIsPaused(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const pauseRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.pause();
      setIsPaused(true);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const resumeRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "paused") {
      mediaRecorderRef.current.resume();
      setIsPaused(false);
      timerRef.current = setInterval(() => {
        setDuration(prev => prev + 1);
      }, 1000);
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      className="card-surface p-6 space-y-5"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Live Recording</h2>
        <span className="text-xs text-slate-500 dark:text-white/50">Real-time capture</span>
      </div>

      <div className="relative">
        <div className="flex flex-col items-center justify-center gap-4 border border-dashed border-slate-200/70 dark:border-white/20 rounded-2xl px-4 py-8">
          <div className="relative">
            <div className={`w-20 h-20 rounded-full ${isRecording ? "bg-rose-500/20" : "bg-accent-500/20"} flex items-center justify-center`}>
              <span className="text-3xl">{isRecording ? "🎙️" : "🎤"}</span>
            </div>
            {isRecording && (
              <motion.div
                className="absolute inset-0 rounded-full border-2 border-rose-500"
                animate={{
                  scale: [1, 1.3, 1],
                  opacity: [0.8, 0, 0.8]
                }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  ease: "easeOut"
                }}
              />
            )}
          </div>

          <AnimatePresence mode="wait">
            {isRecording ? (
              <motion.div
                key="recording"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="text-center space-y-2"
              >
                <p className="text-2xl font-mono font-semibold text-slate-900 dark:text-white">{formatTime(duration)}</p>
                <p className="text-xs text-slate-500 dark:text-white/60">
                  {isPaused ? "Recording paused" : "Recording in progress..."}
                </p>
              </motion.div>
            ) : hasRecording ? (
              <motion.div
                key="ready-to-analyze"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="text-center space-y-1"
              >
                <p className="text-sm text-emerald-600 dark:text-emerald-400 font-semibold">✓ Recording Saved</p>
                <p className="text-xs text-slate-500 dark:text-white/50">Click "Analyze Recording" below</p>
              </motion.div>
            ) : (
              <motion.div
                key="ready"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="text-center space-y-1"
              >
                <p className="text-sm text-slate-700 dark:text-white/80">Ready to record</p>
                <p className="text-xs text-slate-500 dark:text-white/50">Click start to begin</p>
              </motion.div>
            )}
          </AnimatePresence>

          {isRecording && (
            <div className="w-full max-w-xs">
              <div className="h-2 bg-slate-200/80 dark:bg-white/10 rounded-full overflow-hidden">
                <motion.div
                  className="h-full bg-gradient-to-r from-accent-500 to-rose-500"
                  animate={{
                    width: `${audioLevel * 100}%`
                  }}
                  transition={{ duration: 0.1 }}
                />
              </div>
              <p className="text-xs text-slate-500 dark:text-white/50 text-center mt-2">Audio level</p>
            </div>
          )}
        </div>
      </div>

      <div className="flex gap-3">
        {!isRecording ? (
          <>
            <button
              onClick={startRecording}
              disabled={isProcessing}
              className="flex-1 py-3 rounded-xl bg-gradient-to-r from-accent-600 to-aura-600 text-white text-sm font-semibold shadow-glow hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {hasRecording ? "Record Again" : "Start Recording"}
            </button>
            {hasRecording && (
              <button
                onClick={onAnalyze}
                disabled={isProcessing}
                className="flex-1 py-3 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white text-sm font-semibold shadow-lg hover:brightness-105 disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                {isProcessing ? "Processing..." : "Analyze Recording"}
              </button>
            )}
          </>
        ) : (
          <>
            {!isPaused ? (
              <button
                onClick={pauseRecording}
                className="flex-1 py-3 rounded-xl bg-amber-500/20 border border-amber-500/30 text-sm font-semibold hover:bg-amber-500/30 transition"
              >
                Pause
              </button>
            ) : (
              <button
                onClick={resumeRecording}
                className="flex-1 py-3 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-sm font-semibold hover:bg-emerald-500/30 transition"
              >
                Resume
              </button>
            )}
            <button
              onClick={stopRecording}
              className="flex-1 py-3 rounded-xl bg-rose-500/20 border border-rose-500/30 text-sm font-semibold hover:bg-rose-500/30 transition"
            >
              Stop Recording
            </button>
          </>
        )}
      </div>

      <p className="text-xs text-slate-500 dark:text-white/50 text-center">
        Record clear audio in a quiet environment for best results
      </p>

      <div className="space-y-3 pt-3 border-t border-white/10">
        <p className="text-xs text-white/60 font-medium">Translation Settings</p>
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs text-white/60">
            Target language
            <select
              className="mt-2 w-full bg-base-700/70 border border-white/10 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
              value={targetLang}
              onChange={(event) => setTargetLang(event.target.value)}
              disabled={isRecording}
            >
              <option value="en">🇬🇧 English</option>
              <option value="hi">🇮🇳 Hindi</option>
              <option value="te">🇮🇳 Telugu</option>
            </select>
          </label>
        </div>
      </div>
    </motion.div>
  );
}
