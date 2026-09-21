"""
RESILIA Standalone Sentinel Worker — Phase 3
=============================================
Runs decoupled from the FastAPI web server.
Can run as an ECS Task, Kubernetes DaemonSet, or systemd background service.

Usage:
  python backend/scripts/run_sentinel_worker.py --once
  python backend/scripts/run_sentinel_worker.py --interval 30
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import time

# Ensure backend path is available
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agents.sentinel_agent import sentinel_agent
from app.events.event_bus import event_bus
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (SentinelWorker) %(message)s",
)
logger = logging.getLogger("SentinelWorker")


def handle_sigterm(signum, frame):
    logger.info("Received termination signal %s. Shutting down gracefully…", signum)
    sentinel_agent.stop()
    event_bus.stop()
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="RESILIA Sentinel Autonomous Worker")
    parser.add_argument("--once", action="store_true", help="Execute single network scan pass and exit")
    parser.add_argument("--interval", type=int, default=60, help="Scan interval in seconds (default: 60)")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, handle_sigterm)
    signal.signal(signal.SIGTERM, handle_sigterm)

    logger.info("Initializing RESILIA Sentinel Worker [Env: %s, Bus: %s]…", settings.environment, settings.event_bus_name)
    event_bus.start()
    sentinel_agent.start()

    if args.once:
        logger.info("Running single network scan pass…")
        summary = sentinel_agent.scan_network()
        logger.info("Scan completed: %s", summary)
        sentinel_agent.stop()
        event_bus.stop()
        return

    logger.info("Sentinel worker running continuously (interval: %ds). Press Ctrl+C to terminate.", args.interval)
    try:
        while True:
            time.sleep(args.interval)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down Sentinel worker…")
    finally:
        sentinel_agent.stop()
        event_bus.stop()


if __name__ == "__main__":
    main()
