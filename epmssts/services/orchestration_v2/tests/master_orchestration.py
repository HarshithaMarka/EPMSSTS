"""
Master Orchestration Script - Complete Production Validation Suite

Runs both:
1. Standalone 8-phase systematic validation
2. Live endpoint testing against running server
3. Aggregates all results into formal enterprise audit report
"""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


async def run_production_validation():
    """Import and run production harness."""
    logger.info("\n" + "=" * 80)
    logger.info("PHASE: Running 8-Phase Systematic Validation")
    logger.info("=" * 80)
    
    try:
        from production_harness import HarnessPipeline
        
        harness = HarnessPipeline(output_dir="./validation_reports")
        audit = await harness.run_all_phases()
        report_path = harness.save_report(audit)
        
        logger.info(f"\n✓ Systematic validation complete")
        logger.info(f"  Report: {report_path}")
        
        return {
            "phase": "systematic_validation",
            "status": "completed",
            "report": report_path,
            "score": audit.production_readiness_score,
            "recommendation": audit.deployment_recommendation,
            "audit": audit,
        }
    except Exception as e:
        logger.error(f"✗ Systematic validation failed: {str(e)}")
        return {
            "phase": "systematic_validation",
            "status": "failed",
            "error": str(e),
        }


async def run_live_endpoint_validation():
    """Import and run live endpoint harness."""
    logger.info("\n" + "=" * 80)
    logger.info("PHASE: Running Live Endpoint Validation")
    logger.info("=" * 80)
    
    try:
        from live_endpoint_harness import RealEndpointHarness
        
        async with RealEndpointHarness(base_url="http://localhost:8000") as harness:
            results = await harness.run_live_validation()
        
        logger.info(f"\n✓ Live endpoint validation complete")
        
        return {
            "phase": "live_endpoints",
            "status": "completed",
            "results": results,
        }
    except Exception as e:
        logger.warning(f"⚠ Live endpoint validation failed (server may not be running): {str(e)}")
        return {
            "phase": "live_endpoints",
            "status": "failed",
            "error": str(e),
            "note": "This is non-fatal - server may not be running yet",
        }


def aggregate_results(
    systematic: Dict[str, Any],
    live: Dict[str, Any]
) -> Dict[str, Any]:
    """Aggregate results from both validation phases."""
    aggregated = {
        "timestamp": datetime.now().isoformat(),
        "systematic_validation": systematic,
        "live_endpoint_validation": live,
        "overall_assessment": {
            "systematic_status": systematic.get("status"),
            "live_status": live.get("status"),
            "production_readiness_score": systematic.get("score", 0),
            "deployment_recommendation": systematic.get("recommendation", "unknown"),
        },
    }
    
    return aggregated


def generate_executive_summary(aggregated: Dict[str, Any]) -> str:
    """Generate executive summary of validation results."""
    systematic = aggregated.get("systematic_validation", {})
    live = aggregated.get("live_endpoint_validation", {})
    overall = aggregated.get("overall_assessment", {})
    
    summary = f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                 EPMSSTS PRODUCTION READINESS AUDIT                        ║
║              Enterprise Reliability Validation Report                      ║
╚════════════════════════════════════════════════════════════════════════════╝

TIMESTAMP: {aggregated['timestamp']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXECUTIVE SUMMARY
─────────────────

Production Readiness Score: {overall.get('production_readiness_score', 0)}/100

Deployment Recommendation: {overall.get('deployment_recommendation', 'UNKNOWN').upper()}

System Status: {overall.get('systematic_status', 'UNKNOWN').upper()}

Live Endpoint Status: {overall.get('live_status', 'UNKNOWN').upper()}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SYSTEMATIC VALIDATION (8-PHASE)
───────────────────────────────

Status: {systematic.get('status', 'UNKNOWN').upper()}

Report Location: {systematic.get('report', 'N/A')}

Phases Completed:
"""
    
    if "audit" in systematic:
        audit = systematic["audit"]
        for phase in audit.phases:
            summary += f"\n  └─ Phase {phase.phase_number}: {phase.phase_name:<35} [{phase.status}]"
        
        summary += f"\n\nOverall Assessment:\n"
        summary += f"  • Passes: {sum(1 for p in audit.phases if p.status == 'PASS')}/{len(audit.phases)}\n"
        summary += f"  • Warnings: {sum(1 for p in audit.phases if p.status == 'WARN')}/{len(audit.phases)}\n"
        summary += f"  • Failures: {sum(1 for p in audit.phases if p.status == 'FAIL')}/{len(audit.phases)}\n"
        
        if audit.critical_issues:
            summary += f"\nCritical Issues ({len(audit.critical_issues)}):\n"
            for issue in audit.critical_issues[:5]:
                summary += f"  ✗ {issue}\n"
            if len(audit.critical_issues) > 5:
                summary += f"  ... and {len(audit.critical_issues) - 5} more\n"
        
        if audit.medium_issues:
            summary += f"\nMedium Issues ({len(audit.medium_issues)}):\n"
            for issue in audit.medium_issues[:5]:
                summary += f"  ⚠ {issue}\n"
            if len(audit.medium_issues) > 5:
                summary += f"  ... and {len(audit.medium_issues) - 5} more\n"
    
    summary += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LIVE ENDPOINT VALIDATION
─────────────────────────

Status: {live.get('status', 'UNKNOWN').upper()}
"""
    
    if live.get("status") == "completed":
        results = live.get("results", {})
        summary += f"""
Server Connectivity: ✓ Connected

Endpoint Tests:
  • Total Tests: {results.get('total_tests', 0)}
  • Successful: {results.get('successful', 0)}
  • Failed: {results.get('failed', 0)}
  • Average Latency: {results.get('average_latency_ms', 0):.1f}ms
"""
    elif live.get("status") == "failed":
        summary += f"""
Server Connectivity: ✗ Not responding
Reason: {live.get('error', 'Unknown')}
Note: {live.get('note', 'Server may need to be started')}
"""
    
    summary += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DEPLOYMENT DECISION
───────────────────

Recommendation: {overall.get('deployment_recommendation', 'UNKNOWN').upper()}

Actions:
"""
    
    recommendation = overall.get('deployment_recommendation', '').lower()
    if recommendation == 'staged_rollout':
        summary += """
  1. ✓ System is production-ready
  2. ✓ Begin staged rollout:
     - Deploy to 10% of traffic
     - Monitor metrics for 24 hours
     - Increase to 50% if stable
     - Proceed to 100% if no issues
  3. ✓ Enable alert thresholds per SLA matrix
  4. ✓ Configure horizontal autoscaling (2-10 replicas)
"""
    elif recommendation == 'pilot_only':
        summary += """
  1. ⚠ System requires hardening
  2. ⚠ Actions before production:
     - Address all medium issues
     - Re-run Phase validations
     - Get approval from architecture team
  3. ⚠ Deploy to isolated pilot environment first
  4. ⚠ Extended monitoring (72 hours) before general rollout
"""
    else:
        summary += """
  1. ✗ System NOT production-ready
  2. ✗ Critical actions required:
     - Address all critical issues immediately
     - Escalate to engineering team
     - Do NOT deploy to production
  3. ✗ Re-run full validation after fixes
  4. ✗ Requires approval before retry
"""
    
    summary += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NEXT STEPS
──────────

1. Review full reports in ./validation_reports/
2. For systematic validation details: production_audit_*.json
3. For live endpoint results: See log output above
4. Escalate critical issues to engineering team
5. Re-run validation after fixes: python master_orchestration.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    return summary


async def main():
    """Main orchestration entry point."""
    logger.info("""
╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║       EPMSSTS PRODUCTION HARDENING & RELIABILITY VALIDATION              ║
║                     COMPREHENSIVE AUDIT ORCHESTRATION                    ║
║                                                                          ║
║  Running: 8-Phase Systematic Validation + Live Endpoint Testing         ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
""")

    # Run all validations
    systematic = await run_production_validation()
    live = await run_live_endpoint_validation()

    # Aggregate results
    aggregated = aggregate_results(systematic, live)

    # Generate executive summary
    summary = generate_executive_summary(aggregated)
    logger.info(summary)

    # Save aggregated report
    reports_dir = Path("./validation_reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    report_path = reports_dir / f"master_audit_report_{int(datetime.now().timestamp())}.json"
    with open(report_path, "w") as f:
        json.dump(aggregated, f, indent=2, default=str)
    
    summary_path = reports_dir / f"executive_summary_{int(datetime.now().timestamp())}.txt"
    with open(summary_path, "w") as f:
        f.write(summary)

    logger.info(f"\n✓ Master audit report saved: {report_path}")
    logger.info(f"✓ Executive summary saved: {summary_path}")

    logger.info("\n" + "=" * 80)
    logger.info("ORCHESTRATION COMPLETE")
    logger.info("=" * 80)
    logger.info("\nAll reports available in: ./validation_reports/")
    logger.info("\nFor deployment decision, see executive summary above.")


if __name__ == "__main__":
    asyncio.run(main())
