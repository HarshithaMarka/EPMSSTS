import { motion } from "framer-motion";

const defaultSteps = ["Speech Recognition", "Emotion Analysis", "Dialect Detection", "Translation", "Speech Synthesis"];

export default function Stepper({ currentStep, steps = defaultSteps }) {
  return (
    <div className="flex flex-wrap gap-3">
      {steps.map((step, index) => {
        const isActive = index === currentStep;
        const isDone = index < currentStep;
        return (
          <motion.div
            key={step}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className={`px-3 py-2 rounded-full text-xs font-semibold border transition ${
              isDone
                ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-600 dark:text-emerald-200"
                : isActive
                ? "bg-sky-500/15 border-sky-500/40 text-sky-600 dark:text-sky-200"
                : "bg-white/60 dark:bg-white/5 border-slate-200/70 dark:border-white/10 text-slate-600 dark:text-white/60"
            }`}
          >
            {step}
          </motion.div>
        );
      })}
    </div>
  );
}
