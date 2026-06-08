#!/usr/bin/env python
"""
Quick Runner Script - EPMSSTS Production Validation

Usage:
  python run_validation.py              # Run everything
  python run_validation.py --phases     # Run only 8-phase validation
  python run_validation.py --live       # Run only live endpoint testing
  python run_validation.py --help       # Show help
"""

import sys
import asyncio
import argparse
from pathlib import Path


async def run_all():
    """Run complete validation suite."""
    from epmssts.services.orchestration_v2.tests.master_orchestration import main
    await main()


async def run_phases_only():
    """Run only 8-phase systematic validation."""
    from epmssts.services.orchestration_v2.tests.production_harness import HarnessPipeline
    import json
    from datetime import datetime
    
    print("\n" + "=" * 80)
    print("RUNNING: 8-Phase Systematic Validation Only")
    print("=" * 80)
    
    harness = HarnessPipeline(output_dir="./validation_reports")
    audit = await harness.run_all_phases()
    report_path = harness.save_report(audit)
    
    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)
    print(f"\n✓ Production Readiness Score: {audit.production_readiness_score}/100")
    print(f"✓ Recommendation: {audit.deployment_recommendation.upper()}")
    print(f"✓ Report saved: {report_path}")
    print(f"\nCritical Issues: {len(audit.critical_issues)}")
    print(f"Medium Issues: {len(audit.medium_issues)}")
    print(f"Low Issues: {len(audit.low_issues)}")
    
    if audit.critical_issues:
        print("\nCritical Issues:")
        for issue in audit.critical_issues:
            print(f"  ✗ {issue}")


async def run_live_only():
    """Run only live endpoint testing."""
    from epmssts.services.orchestration_v2.tests.live_endpoint_harness import RealEndpointHarness
    
    print("\n" + "=" * 80)
    print("RUNNING: Live Endpoint Testing Only")
    print("=" * 80)
    print("Attempting to connect to http://localhost:8000...")
    
    try:
        async with RealEndpointHarness(base_url="http://localhost:8000") as harness:
            results = await harness.run_live_validation()
        
        print("\n" + "=" * 80)
        print("LIVE ENDPOINT TESTING COMPLETE")
        print("=" * 80)
        
        if results["connected"]:
            print(f"\n✓ Server connected: http://localhost:8000")
            print(f"✓ Tests run: {results['total_tests']}")
            print(f"✓ Successful: {results['successful']}")
            print(f"✓ Failed: {results['failed']}")
            print(f"✓ Average latency: {results['average_latency_ms']:.1f}ms")
        else:
            print(f"\n✗ Could not connect to server")
            print(f"  Error: {results.get('error', 'Unknown')}")
            print(f"  Note: Make sure server is running:")
            print(f"    uvicorn epmssts.api.main:app --reload")
    
    except Exception as e:
        print(f"\n✗ Live testing failed: {str(e)}")
        print(f"  Make sure server is running on http://localhost:8000")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="EPMSSTS Production Validation Runner"
    )
    parser.add_argument(
        "--phases",
        action="store_true",
        help="Run only 8-phase systematic validation"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run only live endpoint testing"
    )
    parser.add_argument(
        "--help-detailed",
        action="store_true",
        help="Show detailed help about validation phases"
    )
    
    args = parser.parse_args()
    
    if args.help_detailed:
        print("""
EPMSSTS Production Validation Suite
====================================

8 Validation Phases:
  1. SLA & Latency Validation     - Measure latency under load
  2. Failure Isolation Testing    - Verify circuit breaker behavior
  3. Confidence Propagation Audit - Validate confidence aggregation
  4. Observability & Metrics Audit- Verify metrics collection
  5. Concurrency & Memory Test    - Test high-concurrency handling
  6. Security Validation          - Test security guards
  7. Redis Fallback Test          - Verify fallback behavior
  8. Production Readiness Score   - Compute final score

Usage:
  python run_validation.py              # Run both systematic + live
  python run_validation.py --phases     # Run only 8-phase validation
  python run_validation.py --live       # Run only live endpoint testing

Output:
  All reports saved to ./validation_reports/
  
  - production_audit_[timestamp].json    (8-phase results)
  - master_audit_report_[timestamp].json (complete audit)
  - executive_summary_[timestamp].txt    (human-readable summary)

For detailed information, see:
  epmssts/services/orchestration_v2/tests/PRODUCTION_VALIDATION_GUIDE.md
        """)
        return
    
    try:
        if args.phases:
            await run_phases_only()
        elif args.live:
            await run_live_only()
        else:
            await run_all()
    
    except KeyboardInterrupt:
        print("\n\n⚠ Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Validation failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
