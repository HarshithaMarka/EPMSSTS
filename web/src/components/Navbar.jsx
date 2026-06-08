import { motion } from "framer-motion";

export default function Navbar({ online, onToggleTheme, theme }) {
  return (
    <motion.nav
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full px-6 py-5 flex items-center justify-between border-b border-slate-200/60 dark:border-white/10 bg-white/70 dark:bg-base-900/80 backdrop-blur sticky top-0 z-50"
    >
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent-500 to-aura-600 flex items-center justify-center font-bold text-lg text-white">
          E
        </div>
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-white">EPMSSTS</h1>
          <p className="text-xs text-slate-500 dark:text-white/60">Emotion-Preserving Speech AI</p>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-white/70 bg-white/70 dark:bg-white/5 px-3 py-2 rounded-full border border-slate-200/70 dark:border-white/10">
          <span className={`dot-pulse ${online ? "bg-emerald-400" : "bg-rose-400"}`} />
          <span className="text-xs">{online ? "Online" : "Offline"}</span>
        </div>
        <button
          onClick={onToggleTheme}
          className="text-xs px-3 py-2 rounded-full border border-slate-200/70 dark:border-white/10 hover:bg-white/70 dark:hover:bg-white/10"
        >
          {theme === "dark" ? "Light Mode" : "Dark Mode"}
        </button>
      </div>
    </motion.nav>
  );
}
