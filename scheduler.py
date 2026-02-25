from apscheduler.schedulers.background import BackgroundScheduler
from cam_utils import capture_snapshot
from timelapse_utils import stitch_timelapse, stitch_weekly_timelapse, cleanup_old_data
from settings import SNAPSHOT_INTERVAL_MIN, TIMELAPSE_STITCH_HOUR
from logging_setup import setup_logger

logger = setup_logger("scheduler")
scheduler = BackgroundScheduler()


def start_scheduler():
    scheduler.add_job(capture_snapshot, "interval", minutes=SNAPSHOT_INTERVAL_MIN, id="snapshot_job", replace_existing=True)
    logger.info(f"Snapshot job scheduled every {SNAPSHOT_INTERVAL_MIN} minutes")
    scheduler.add_job(stitch_timelapse, "cron", hour=TIMELAPSE_STITCH_HOUR, minute=0, id="timelapse_job", replace_existing=True)
    logger.info(f"Timelapse stitch job scheduled daily at {TIMELAPSE_STITCH_HOUR}:00")
    scheduler.add_job(stitch_weekly_timelapse, "cron", day_of_week="sun", hour=TIMELAPSE_STITCH_HOUR, minute=30, id="weekly_timelapse_job", replace_existing=True)
    logger.info("Weekly timelapse stitch job scheduled Sundays at %d:30", TIMELAPSE_STITCH_HOUR)
    scheduler.add_job(cleanup_old_data, "cron", day_of_week="sun", hour=TIMELAPSE_STITCH_HOUR, minute=45, id="cleanup_job", replace_existing=True)
    logger.info("Cleanup job scheduled Sundays at %d:45", TIMELAPSE_STITCH_HOUR)
    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler():
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
