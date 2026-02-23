from utils.decorators import task
from utils.base_runner import TaskContext
from urllib.parse import urljoin
import requests
from datetime import datetime, timedelta


@task(
    name="delete_old_jobs",
    title="Delete old jobs",
    description="Delete old jobs to clear up space",
    type="collector"
)
def delete_old_jobs(self, ctx: TaskContext):
    ctx.add_log("Deleting jobs older than 14 days")
    url = ctx.config.get("INTEGRATIONS_BASE_URL")
    cutoff = datetime.utcnow() - timedelta(days=14)
    response = requests.delete(
        urljoin(url, "/jobs"),
        params={"after": cutoff.isoformat()}
    )
    if not response.ok:
        ctx.add_log(f"Failed to delete jobs: {response.text}")
    msg = f"Deleted {response.json()['deleted']} jobs"
    ctx.add_log(msg)

    return {
        "message": msg,
        "data": {
            "response": msg
        }
    }