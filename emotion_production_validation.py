#!/usr/bin/env python3
"""
Master Emotion System Advanced Validation

Orchestrates all validation phases and generates comprehensive production readiness report:

Phase 1: Over-correction check
Phase 2: Volume invariance  
Phase 3: Temporal stability
Phase 4: TTS expressiveness
Phase 5: Executive demo simulation

Generates:
- Confusion matrix
- Per-class accuracy
- Over-correction metrics
- Stability scores
- Round-trip preservation
- Production readiness score
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("emotion.master.validation")


class MasterValidator:
    """Orchestrates all validation phases."""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("outputs/validation_reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.report_data = {
            "phase1": None,
            "phase2": None,
            "phase3": None,
            "phase4": None,
            "phase5": None,
            "final_score": None
        }
    
    async def run_all_phases(self):
        """Execute all validation phases."""
        
        # Import validators
        from emotion_advanced_validation import AdvancedEmotionValidator
        from emotion_tts_roundtrip_validation import TTSEmotionValidator
        
        logger.info("=" * 80)
        logger.info("MASTER EMOTION SYSTEM VALIDATION")
        logger.info("=" * 80)
        logger.info("\nRunning comprehensive validation suite...")
        logger.info("This will test over-correction, volume invariance, stability,")
        logger.info("TTS expressiveness, and executive demo scenarios.\n")
        
        # ================================================================
        # PHASES 1-3: Core emotion detection validation
        # ================================================================
        
        logger.info("\n" + "▶" * 40)
        logger.info("RUNNING PHASES 1-3: EMOTION DETECTION VALIDATION")
        logger.info("▶" * 40)
        
        emotion_validator = AdvancedEmotionValidator()
        
        # Phase 1
        phase1_results = emotion_validator.phase1_over_correction_check()
        self.report_data["phase1"] = phase1_results
        
        # Phase 2
        phase2_results = emotion_validator.phase2_volume_invariance()
        self.report_data["phase2"] = phase2_results
        
        # Phase 3
        phase3_results = emotion_validator.phase3_temporal_stability()
        self.report_data["phase3"] = phase3_results
        
        # Generate emotion detection report
        emotion_report = emotion_validator.generate_report(
            phase1_results, phase2_results, phase3_results
        )
        
        # ================================================================
        # PHASES 4-5: TTS emotion validation
        # ================================================================
        
        logger.info("\n" + "▶" * 40)
        logger.info("RUNNING PHASES 4-5: TTS EMOTION VALIDATION")
        logger.info("▶" * 40)
        
        tts_validator = TTSEmotionValidator()
        
        # Phase 4
        phase4_results = await tts_validator.phase4_tts_expressiveness()
        self.report_data["phase4"] = {
            "preservation_rate": phase4_results["preservation_rate"],
            "avg_consistency": phase4_results["avg_consistency"],
            "avg_latency_ms": phase4_results["avg_latency_ms"]
        }
        
        # Phase 5
        phase5_results = await tts_validator.phase5_executive_demo()
        self.report_data["phase5"] = phase5_results
        
        # ================================================================
        # FINAL REPORT GENERATION
        # ================================================================
        
        final_score = self._calculate_final_score(emotion_report, phase4_results, phase5_results)
        self.report_data["final_score"] = final_score
        
        # Save detailed JSON report
        self._save_json_report()
        
        # Generate markdown report
        self._generate_markdown_report(emotion_report, phase4_results, phase5_results, final_score)
        
        return final_score
    
    def _calculate_final_score(
        self,
        emotion_report: Dict,
        phase4_results: Dict,
        phase5_results: Dict
    ) -> Dict:
        """Calculate overall production readiness score."""
        
        # Component scores
        emotion_detection_score = emotion_report["production_score"]
        
        # Check if TTS phases were skipped
        tts_skipped = phase4_results.get("skipped", False) or phase5_results.get("skipped", False)
        
        if tts_skipped:
            # If TTS validation was skipped, base score only on emotion detection
            logger.warning("⚠️  TTS validation skipped - score based on emotion detection only")
            
            weights = {
                "emotion_detection": 1.00,
                "tts_preservation": 0.00,
                "tts_naturalness": 0.00,
                "latency": 0.00
            }
            
            final_score = emotion_detection_score
            
            return {
                "components": {
                    "emotion_detection": emotion_detection_score,
                    "tts_preservation": 0.0,
                    "tts_naturalness": 0.0,
                    "latency": 0.0
                },
                "weights": weights,
                "final_score": final_score,
                "grade": self._get_grade(final_score),
                "tts_skipped": True
            }
        
        # Normal case with TTS validation
        tts_preservation_score = phase4_results["preservation_rate"]
        tts_naturalness_score = phase5_results["naturalness_score"]
        latency_score = min(
            1.0,
            4000 / max(phase4_results["avg_latency_ms"], phase5_results["avg_latency_ms"])
        )
        
        # Weighted final score
        weights = {
            "emotion_detection": 0.40,
            "tts_preservation": 0.25,
            "tts_naturalness": 0.20,
            "latency": 0.15
        }
        
        final_score = (
            emotion_detection_score * weights["emotion_detection"] +
            tts_preservation_score * weights["tts_preservation"] +
            tts_naturalness_score * weights["tts_naturalness"] +
            latency_score * weights["latency"]
        )
        
        return {
            "components": {
                "emotion_detection": emotion_detection_score,
                "tts_preservation": tts_preservation_score,
                "tts_naturalness": tts_naturalness_score,
                "latency": latency_score
            },
            "weights": weights,
            "final_score": final_score,
            "grade": self._get_grade(final_score),
            "tts_skipped": False
        }
    
    def _get_grade(self, score: float) -> str:
        """Convert score to letter grade."""
        if score >= 0.90:
            return "A+ (Excellent)"
        elif score >= 0.85:
            return "A (Very Good)"
        elif score >= 0.80:
            return "B+ (Good)"
        elif score >= 0.70:
            return "B (Acceptable)"
        elif score >= 0.60:
            return "C (Needs Improvement)"
        else:
            return "F (Not Ready)"
    
    def _save_json_report(self):
        """Save detailed JSON report."""
        json_path = self.output_dir / "validation_report.json"
        
        # Serialize (handle non-serializable objects)
        serializable_data = {}
        for phase, data in self.report_data.items():
            if data is None:
                serializable_data[phase] = None
            elif isinstance(data, dict):
                serializable_data[phase] = {
                    k: (v if isinstance(v, (str, int, float, bool, list, dict, type(None))) else str(v))
                    for k, v in data.items()
                }
            else:
                serializable_data[phase] = str(data)
        
        with open(json_path, "w") as f:
            json.dump(serializable_data, f, indent=2)
        
        logger.info(f"\n📄 JSON report saved: {json_path}")
    
    def _generate_markdown_report(
        self,
        emotion_report: Dict,
        phase4_results: Dict,
        phase5_results: Dict,
        final_score: Dict
    ):
        """Generate comprehensive markdown report."""
        
        report_path = self.output_dir / "ADVANCED_VALIDATION_REPORT.md"
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# Advanced Emotion Detection System Validation Report\n\n")
            f.write("**Validation Date:** {}\n\n".format("2026-03-01"))
            f.write("**System:** EPMSSTS Emotion-Preserving Speech Translation\n\n")
            f.write("---\n\n")
            
            # Executive Summary
            f.write("## Executive Summary\n\n")
            f.write(f"**Final Production Readiness Score:** {final_score['final_score']:.1%} ({final_score['grade']})\n\n")
            
            if final_score['final_score'] >= 0.85:
                f.write("✅ **VERDICT:** System is production-ready and shows professional behavior.\n\n")
            elif final_score['final_score'] >= 0.70:
                f.write("⚠️ **VERDICT:** System is acceptable for production with minor improvements.\n\n")
            else:
                f.write("❌ **VERDICT:** System requires significant improvements before production.\n\n")
            
            # Score Breakdown
            f.write("### Score Breakdown\n\n")
            f.write("| Component | Score | Weight | Contribution |\n")
            f.write("|-----------|-------|--------|-------------|\n")
            for component, score in final_score['components'].items():
                weight = final_score['weights'][component]
                contribution = score * weight
                f.write(f"| {component.replace('_', ' ').title()} | {score:.1%} | {weight:.0%} | {contribution:.1%} |\n")
            f.write(f"| **TOTAL** | **{final_score['final_score']:.1%}** | **100%** | **{final_score['final_score']:.1%}** |\n\n")
            
            # Phase 1: Over-Correction Check
            f.write("---\n\n")
            f.write("## Phase 1: Over-Correction Check\n\n")
            f.write("**Objective:** Ensure system does not over-correct genuine emotions to neutral.\n\n")
            
            f.write("### Results\n\n")
            over_correction_rate = emotion_report.get("over_correction_rate", 0.0)
            f.write(f"- **Over-correction rate:** {over_correction_rate:.2%}\n")
            
            if 0.05 <= over_correction_rate <= 0.20:
                f.write("  - ✅ **OPTIMAL RANGE** - Rules are balanced\n")
            elif over_correction_rate > 0.20:
                f.write("  - ⚠️ **TOO HIGH** - System may be too conservative\n")
            else:
                f.write("  - ⚠️ **TOO LOW** - Rules may not be engaging properly\n")
            
            f.write("\n### Confusion Matrix\n\n")
            f.write("| Emotion | Precision | Recall | F1-Score |\n")
            f.write("|---------|-----------|--------|----------|\n")
            
            cm = emotion_report["confusion_matrix"]
            for emotion in ["neutral", "happy", "sad", "angry", "fearful"]:
                precision = cm["precision"].get(emotion, 0.0)
                recall = cm["recall"].get(emotion, 0.0)
                f1 = cm["f1_score"].get(emotion, 0.0)
                f.write(f"| {emotion.capitalize()} | {precision:.2%} | {recall:.2%} | {f1:.2%} |\n")
            
            f.write(f"\n**Overall Accuracy:** {cm['accuracy']:.2%}\n\n")
            
            # Phase 2: Volume Invariance
            f.write("---\n\n")
            f.write("## Phase 2: Volume Invariance Test\n\n")
            f.write("**Objective:** Verify predictions remain consistent across volume levels.\n\n")
            
            invariance_score = emotion_report.get("volume_invariance", 0.0)
            f.write(f"**Invariance Score:** {invariance_score:.2%}\n\n")
            
            if invariance_score >= 0.70:
                f.write("✅ **GOOD** - Predictions stable across volumes\n\n")
            else:
                f.write("⚠️ **POOR** - Predictions vary too much with volume\n\n")
            
            # Phase 3: Temporal Stability
            f.write("---\n\n")
            f.write("## Phase 3: Temporal Stability Test\n\n")
            f.write("**Objective:** Ensure predictions don't randomly flip between emotions.\n\n")
            
            stability_score = emotion_report.get("temporal_stability", 0.0)
            f.write(f"**Stability Score:** {stability_score:.2%}\n\n")
            
            if stability_score >= 0.70:
                f.write("✅ **STABLE** - No additional smoothing required\n\n")
            else:
                f.write("⚠️ **UNSTABLE** - Consider enabling temporal smoothing (EMA)\n\n")
                f.write("**Recommendation:** Implement emotion smoothing:\n")
                f.write("```python\n")
                f.write("emotion_t = 0.7 * previous_emotion + 0.3 * current_emotion\n")
                f.write("```\n\n")
            
            # Phase 4: TTS Expressiveness
            f.write("---\n\n")
            f.write("## Phase 4: TTS Expressiveness Validation\n\n")
            f.write("**Objective:** Verify emotion affects TTS prosody and is preserved in round-trip.\n\n")
            
            preservation_rate = phase4_results["preservation_rate"]
            avg_consistency = phase4_results["avg_consistency"]
            
            f.write(f"**Preservation Rate:** {preservation_rate:.1%}\n\n")
            f.write(f"**Average Consistency:** {avg_consistency:.2f}\n\n")
            
            if preservation_rate >= 0.70:
                f.write("✅ **GOOD** - Emotion preserved in TTS synthesis\n\n")
            else:
                f.write("⚠️ **POOR** - Emotion not well preserved in TTS\n\n")
                f.write("**Recommendations:**\n")
                f.write("- Implement emotion-aware TTS model\n")
                f.write("- Apply prosody modifications (pitch, rate, energy)\n")
                f.write("- Consider SSML or prosody tags\n\n")
            
            # Phase 5: Executive Demo
            f.write("---\n\n")
            f.write("## Phase 5: Executive Demo Simulation\n\n")
            f.write("**Objective:** Validate end-to-end experience feels natural and professional.\n\n")
            
            naturalness_score = phase5_results["naturalness_score"]
            avg_latency = phase5_results["avg_latency_ms"]
            robotic_warnings = phase5_results.get("robotic_warnings", 0)
            
            f.write(f"**Naturalness Score:** {naturalness_score:.2f}/1.0\n\n")
            f.write(f"**Average Latency:** {avg_latency:.0f}ms\n\n")
            f.write(f"**Robotic Warnings:** {robotic_warnings}\n\n")
            
            if naturalness_score >= 0.70:
                f.write("✅ **NATURAL** - System sounds professional\n\n")
            else:
                f.write("⚠️ **ROBOTIC** - System needs improvement\n\n")
            
            if avg_latency < 4000:
                f.write("✅ **LATENCY OK** - Acceptable for real-time use (<4s)\n\n")
            else:
                f.write("⚠️ **LATENCY HIGH** - May feel sluggish (>4s)\n\n")
            
            # Key Findings
            f.write("---\n\n")
            f.write("## Key Findings\n\n")
            
            f.write("### ✅ Strengths\n\n")
            
            if emotion_report["confusion_matrix"]["accuracy"] >= 0.70:
                f.write("- Strong emotion detection accuracy\n")
            if over_correction_rate >= 0.05 and over_correction_rate <= 0.20:
                f.write("- Well-balanced override rules (not over-correcting)\n")
            if invariance_score >= 0.70:
                f.write("- Volume-invariant predictions\n")
            if stability_score >= 0.70:
                f.write("- Temporally stable predictions\n")
            if preservation_rate >= 0.70:
                f.write("- Emotion preserved in TTS round-trip\n")
            if naturalness_score >= 0.70:
                f.write("- Natural-sounding output\n")
            
            f.write("\n### ⚠️ Areas for Improvement\n\n")
            
            if emotion_report["confusion_matrix"]["accuracy"] < 0.70:
                f.write("- Emotion detection accuracy below target\n")
            if over_correction_rate > 0.20:
                f.write("- Over-correcting too often - relax override rules\n")
            elif over_correction_rate < 0.05:
                f.write("- Under-correcting - override rules may not trigger\n")
            if invariance_score < 0.70:
                f.write("- Predictions affected by volume - improve normalization\n")
            if stability_score < 0.70:
                f.write("- Predictions unstable - implement temporal smoothing\n")
            if preservation_rate < 0.70:
                f.write("- Emotion not preserved in TTS - need emotion-aware synthesis\n")
            if naturalness_score < 0.70:
                f.write("- Output sounds robotic - improve prosody\n")
            if avg_latency >= 4000:
                f.write("- Latency too high - optimize pipeline\n")
            
            # Recommendations
            f.write("\n---\n\n")
            f.write("## Recommendations for Production\n\n")
            
            if final_score['final_score'] >= 0.85:
                f.write("The system demonstrates professional behavior and is ready for production deployment.\n\n")
                f.write("**Next Steps:**\n")
                f.write("1. Deploy to staging environment\n")
                f.write("2. Monitor real-world usage metrics\n")
                f.write("3. Collect user feedback\n")
                f.write("4. Fine-tune thresholds based on production data\n\n")
            
            elif final_score['final_score'] >= 0.70:
                f.write("The system shows promise but requires minor improvements before production.\n\n")
                f.write("**Required Actions:**\n")
                
                if preservation_rate < 0.70:
                    f.write("1. Implement emotion-aware TTS or prosody modification\n")
                if naturalness_score < 0.70:
                    f.write("2. Improve dynamic range and naturalness of synthesis\n")
                if stability_score < 0.70:
                    f.write("3. Add temporal smoothing for stability\n")
                if avg_latency >= 4000:
                    f.write("4. Optimize pipeline for faster processing\n")
                
                f.write("\n")
            
            else:
                f.write("The system requires significant improvements before production deployment.\n\n")
                f.write("**Critical Actions Required:**\n")
                f.write("1. Review and improve emotion detection accuracy\n")
                f.write("2. Calibrate override rules to prevent over/under-correction\n")
                f.write("3. Implement TTS emotion preservation\n")
                f.write("4. Optimize latency\n\n")
            
            # Conclusion
            f.write("---\n\n")
            f.write("## Conclusion\n\n")
            
            f.write(f"The advanced validation suite tested {self.report_data['phase1']['total_tests'] if self.report_data['phase1'] else 'multiple'} ")
            f.write("emotion detection scenarios, volume invariance, temporal stability, ")
            f.write("TTS round-trip preservation, and end-to-end demo scenarios.\n\n")
            
            if final_score['final_score'] >= 0.85:
                f.write("**The system behaves like a real emotional translation product, not a rule-based hack.**\n\n")
                f.write("✅ **APPROVED FOR PRODUCTION**\n\n")
            elif final_score['final_score'] >= 0.70:
                f.write("The system shows professional behavior with minor gaps.\n\n")
                f.write("⚠️ **CONDITIONAL APPROVAL** - Address identified issues before launch\n\n")
            else:
                f.write("The system requires substantial improvements.\n\n")
                f.write("❌ **NOT APPROVED** - Continue development\n\n")
        
        logger.info(f"📄 Markdown report saved: {report_path}")
        
        return report_path


async def main():
    """Run master validation suite."""
    
    validator = MasterValidator()
    
    try:
        final_score = await validator.run_all_phases()
        
        logger.info("\n" + "=" * 80)
        logger.info("VALIDATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"\n🎯 FINAL PRODUCTION READINESS SCORE: {final_score['final_score']:.1%}")
        logger.info(f"   Grade: {final_score['grade']}")
        
        if final_score['final_score'] >= 0.85:
            logger.info("\n✅ SYSTEM IS PRODUCTION-READY")
            return 0
        elif final_score['final_score'] >= 0.70:
            logger.warning("\n⚠️  SYSTEM NEEDS MINOR IMPROVEMENTS")
            return 0
        else:
            logger.error("\n❌ SYSTEM NOT READY FOR PRODUCTION")
            return 1
    
    except Exception as e:
        logger.error(f"\n❌ VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
