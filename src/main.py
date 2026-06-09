"""Entry point — runs the generation pipeline in single or daily mode."""

import logging
import sys
import time

import schedule

from src.config_loader import get_config
from src.pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


def job() -> dict:
    """Wrapper around run_pipeline for the scheduler."""
    try:
        result = run_pipeline()
        logger.info("Job completed: %s", result.get("folder_path", "?"))
        return result
    except Exception:
        logger.exception("Job failed")
        raise


def run_single() -> None:
    """Single execution mode — run once and exit."""
    logger.info("Starting single execution ...")
    job()
    logger.info("Done.")


def run_daily(daily_time: str) -> None:
    """Daily mode — schedule the pipeline and keep the process running."""
    logger.info("Starting daily mode, scheduled at %s ...", daily_time)
    schedule.every().day.at(daily_time).do(job)

    # Run once immediately on startup
    logger.info("Running initial job ...")
    job()

    logger.info("Entering scheduler loop. Press Ctrl+C to exit.")
    while True:
        schedule.run_pending()
        time.sleep(60)


def main() -> None:
    """Parse config and dispatch to the correct mode."""
    try:
        cfg = get_config()
    except (FileNotFoundError, ValueError) as e:
        logger.error("Configuration error: %s", e)
        sys.exit(1)

    mode = cfg.get("schedule", {}).get("mode", "single")
    daily_time = cfg.get("schedule", {}).get("daily_time", "02:00")

    try:
        if mode == "daily":
            run_daily(daily_time)
        else:
            run_single()
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
