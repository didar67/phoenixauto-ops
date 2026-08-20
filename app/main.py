"""
PhoenixAuto-Ops Main Entry Point
===============================

Starts the monitoring engine.
Can be run manually or via cron.
"""

import signal

from app.engine import MonitoringEngine
from app.utils.logger import logger


def main() -> None:
    """Main entry point for the PhoenixAuto-Ops system."""
    logger.info("PhoenixAuto-Ops starting...")

    try:
        engine = MonitoringEngine()

        # Docker sends SIGTERM on `docker stop` / `docker compose down`, not
        # SIGINT - KeyboardInterrupt alone never fires in that path, so the
        # container was previously getting SIGKILL'd with no shutdown log at
        # all once the compose stop_grace_period ran out.

        def _handle_sigterm(signum, frame):
            logger.info("Received shutdown signal. Stopping gracefully.")
            engine.shutdown()

        signal.signal(signal.SIGTERM, _handle_sigterm)
        logger.info("Entering continuous monitoring mode")
        engine.run_forever()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal. Stopping gracefully.")
    except Exception as e:
        logger.critical("Fatal error in main loop", extra={"error": str(e)})
        raise


if __name__ == "__main__":
    main()
