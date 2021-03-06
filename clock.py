import schedule
import time
import redis
from rq import Queue

from dos_status_monitor import monitor, probes, config, slack
from dos_status_monitor import logger
from dos_status_monitor import housekeeping


# Set up RQ queue
conn = redis.from_url(config.REDIS_URL)
q = Queue(connection=conn)


def add_search_jobs():

    probe_list = probes.get_watched_search_list()

    search_job_count = 0

    for probe in probe_list:
        q.enqueue(
            monitor.snapshot_service_search, probe, ttl=f"{config.CHECK_RATE_MINUTES}m"
        )
        search_job_count += 1

    logger.info(
        f"{search_job_count} search probes configured to "
        f"run every {config.CHECK_RATE_MINUTES} minute(s)."
    )


def add_service_jobs():

    service_list = probes.get_watched_service_list()

    service_job_count = 0

    for service in service_list:

        q.enqueue(
            monitor.snapshot_single_service,
            service["id"],
            service["search_role"],
            ttl=f"{config.CHECK_RATE_MINUTES}m",
        )

        service_job_count += 1

    logger.info(
        f"{service_job_count} service probes configured to "
        f"run every {config.CHECK_RATE_MINUTES} minute(s)."
    )


def add_service_status_job():

    if config.SLACK_ENABLED:

        q.enqueue(
            slack.send_slack_status_update, ttl=f"{config.STATUS_UPDATE_RATE_MINUTES}m"
        )

        logger.info(
            "Slack Status Summary will run every "
            f"{config.STATUS_UPDATE_RATE_MINUTES} minute(s)."
        )

    else:
        return


def add_housekeeping_jobs():

    q.enqueue(housekeeping.delete_old_snapshots)
    logger.debug("Added housekeeping jobs to queue")


add_search_jobs()
add_service_jobs()
add_service_status_job()
add_housekeeping_jobs()

# Set up the scheduled jobs
schedule.every(config.CHECK_RATE_MINUTES).minutes.do(add_search_jobs)
schedule.every(config.CHECK_RATE_MINUTES).minutes.do(add_service_jobs)
schedule.every(config.STATUS_UPDATE_RATE_MINUTES).minutes.do(add_service_status_job)
schedule.every(1).day.at("23:30:00").do(add_housekeeping_jobs)

while True:
    logger.info(f"Tick!")
    schedule.run_pending()
    time.sleep(60)
