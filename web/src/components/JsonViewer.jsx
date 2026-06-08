import { motion } from "framer-motion";

export default function JsonViewer({ data }) {
  const json = JSON.stringify(data, null, 2);
  const copy = async () => {
    await navigator.clipboard.writeText(json);
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="card-surface p-4"
    >
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-slate-900 dark:text-white">Raw Output</h4>
        <button
          onClick={copy}
          className="text-xs px-3 py-1 rounded-full border border-slate-200/70 dark:border-white/10 hover:bg-white/70 dark:hover:bg-white/10"
        >
          Copy JSON
        </button>
      </div>
      <pre className="text-xs font-mono text-slate-600 dark:text-white/80 whitespace-pre-wrap break-words max-h-64 overflow-auto">
        {json}
      </pre>
    </motion.div>
  );
}
