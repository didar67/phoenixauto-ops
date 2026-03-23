"""
PhoenixAuto-Ops Main Entry Point
===============================

Starts the monitoring engine.
Can be run manually or via cron.
"""

from app.engine import MonitoringEngine
from app.utils.logger import logger


def main() -> None:
    """Main entry point for the PhoenixAuto-Ops system."""
    logger.info("PhoenixAuto-Ops starting...")

    try:
        engine = MonitoringEngine()
        logger.info("Entering continuous monitoring mode")
        engine.run_forever()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal. Stopping gracefully.")
    except Exception as e:
        logger.critical("Fatal error in main loop", extra={"error": str(e)})
        raise

if __name__ == "__main__":
    main()