from utils.decorators import task
from utils.base_runner import TaskContext
import time
import random


@task(
    name="list_buckets",
    title="List all buckets",
    description="Fetch all S3 buckets from AWS",
    type="collector"
)
def list_buckets(self, ctx: TaskContext):
    ctx.add_log("Connecting to AWS S3 API")
    ctx.add_log("Listing all buckets")
    time.sleep(random.uniform(5, 20))
    # Access base context (still works the same)
    token = ctx.base("token")

    # Simulate API call
    api_response = [
        {"name": "bucket_1", "region": "us-east-1", "encrypted": True},
        {"name": "bucket_2", "region": "us-west-2", "encrypted": False}
    ]

    ctx.add_log(f"Found {len(api_response)} buckets")

    return {
        "data": {
            "buckets": api_response,
            "count": len(api_response)
        }
    }