const EMOTION_COLORS = {
  happy: "bg-emotion-happy",
  sad: "bg-emotion-sad",
  angry: "bg-emotion-angry",
  neutral: "bg-emotion-neutral",
  fearful: "bg-emotion-fearful"
};

export default function EmotionBars({ scores = {} }) {
  const entries = Object.entries(scores);
  if (!entries.length) {
    return <p className="text-sm text-slate-500 dark:text-white/60">No emotion scores available.</p>;
  }

  return (
    <div className="space-y-2">
      {entries.map(([label, value]) => (
        <div key={label} className="flex items-center gap-3">
          <span className="w-20 text-xs uppercase tracking-wide text-slate-500 dark:text-white/70">{label}</span>
          <div className="flex-1 h-2 rounded-full bg-slate-200/70 dark:bg-white/10 overflow-hidden">
            <div
              className={`h-full ${EMOTION_COLORS[label] ?? "bg-white/30"}`}
              style={{ width: `${Math.round((value || 0) * 100)}%` }}
            />
          </div>
          <span className="w-10 text-xs text-slate-500 dark:text-white/60">{Math.round((value || 0) * 100)}%</span>
        </div>
      ))}
    </div>
  );
}
