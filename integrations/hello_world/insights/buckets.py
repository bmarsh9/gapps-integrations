from utils.decorators import task
from utils.base_runner import TaskContext
import time
import random

@task(
    name="check_bucket",
    title="Check for specific buckets",
    description="Check if bucket_1 is in list_buckets",
    type="insight",
    severity="high"
)
def check_bucket(self, ctx: TaskContext):
    data = ctx.get_data("list_buckets")
    buckets = data.get("buckets", [])
    time.sleep(random.uniform(5, 20))

    for bucket in buckets:
        if bucket["name"] == "bucket_1":
            return {
                "violation": True,
                "data": {
                    "total_buckets": len(buckets),
                    "all_buckets": buckets
                },
                "message": "Found bucket_1 in bucket list"
            }

    return {
        "data": {
            "total_buckets": len(buckets),
            "all_buckets": buckets
        },
        "message": "bucket_1 not found"
    }