# Creating a New Integration

Integrations are self-contained Python packages that live in the `integrations/` folder of this repo. Each integration is executed by the worker, which pulls this repo from GitHub on startup and runs integrations in isolated virtual environments.

---

## Folder Structure

Every integration must follow this structure:

```
integrations/
  your_integration_name/
    __init__.py
    entry.py
    requirements.txt
    collectors/
      __init__.py
      list_something.py
    insights/
      __init__.py
      check_something.py
```

---

## Step 1 — Add to `integrations.json`

At the root of the repo, add your integration to `integrations.json`. This is the source of truth for what integrations are available and enabled:

```json
[
  {
    "name": "your_integration_name",
    "title": "Your Integration Title",
    "description": "A short description of what this integration does.",
    "enabled": true,
    "schema": {
      "type": "object",
      "required": ["api_key"],
      "properties": {
        "api_key": {
          "type": "string",
          "title": "API Key"
        }
      }
    }
  }
]
```

The `schema` field is a [JSONSchema](https://json-schema.org/) object that defines and validates the config a user must provide when creating a deployment. Any fields your integration needs (API keys, region, account IDs, etc.) should be defined here.

> **Note:** The `name` field must exactly match the folder name under `integrations/`.

---

## Step 2 — Create `entry.py`

`entry.py` is the entrypoint for your integration. It must define a `Runner` class that extends `BaseRunner`:

```python
from utils.task_registry import register_tasks
from utils.base_runner import BaseRunner


class Runner(BaseRunner):
    name = "your_integration_name"  # Must match integrations.json and folder name

    def __init__(self, config):
        config["integration_name"] = self.name
        register_tasks(self.__class__)
        super().__init__(config)

    class StageOne(BaseRunner.StageOne):
        """
        Authentication / setup phase.
        Return a dict of values that will be available to all tasks via ctx.base().
        """
        def start(self):
            return self.authenticate()

        def authenticate(self):
            return {
                "api_key": self.config.get("api_key"),
            }

    class StageTwo(BaseRunner.StageTwo):
        """
        Task execution phase.
        Tasks are dynamically registered here via the @task decorator.
        Do not add task methods manually.
        """
        pass
```

---

## Step 3 — Create Collectors

Collectors gather data and make it available to insights. They run **before** insights. Place collector files in the `collectors/` folder.

```python
# integrations/your_integration_name/collectors/list_items.py

from utils.decorators import task
from utils.base_runner import TaskContext


@task(
    name="list_items",
    title="List Items",
    description="Fetches all items from the API",
    type="collector"
)
def list_items(self, ctx: TaskContext):
    api_key = ctx.base("api_key")

    # Your data fetching logic here
    items = [{"id": "1", "name": "item_1"}]

    return {
        "data": {
            "items": items
        },
        "message": f"Found {len(items)} items"
    }
```

### Collector Return Format

Collectors must return a dict with the following keys:

| Key | Required | Type | Description |
|-----|----------|------|-------------|
| `data` | Yes | dict or list | The collected data |
| `message` | No | str | A human readable summary |

---

## Step 4 — Create Insights

Insights analyze data collected by collectors and flag violations. They run **after** all collectors. Place insight files in the `insights/` folder.

```python
# integrations/your_integration_name/insights/check_item.py

from utils.decorators import task
from utils.base_runner import TaskContext


@task(
    name="check_item",
    title="Check for specific item",
    description="Checks if item_1 exists in the list",
    type="insight",
    severity="high"
)
def check_item(self, ctx: TaskContext):
    data = ctx.get_data("list_items")
    items = data.get("items", [])

    for item in items:
        if item["name"] == "item_1":
            return {
                "violation": True,
                "data": {
                    "total_items": len(items),
                    "items": items
                },
                "message": "Found item_1 in item list"
            }

    return {
        "violation": False,
        "data": {
            "total_items": len(items),
            "items": items
        },
        "message": "item_1 not found"
    }
```

### Insight Return Format

Insights must return a dict with the following keys:

| Key | Required | Type | Description |
|-----|----------|------|-------------|
| `data` | Yes | dict or list | The result data |
| `violation` | No | bool | Whether a violation was detected. Defaults to `False` |
| `message` | No | str | A human readable summary |

> **Note:** If `violation: True` is returned, a violation record is automatically created on the server.

---

## Step 5 — Create `requirements.txt`

List any Python packages your integration needs beyond the base dependencies:

```
boto3==1.26.0
```

Base dependencies (like `requests`, `jsonschema`, etc.) are already installed in every venv and do not need to be listed here.

---

## Step 6 — Register the Integration in the Database

Once your changes are merged to `main`, call the init endpoint on the API to register the integration in the database:

```bash
curl -X POST http://your-api-host/init-integrations
```

This will create or update the integration record based on `integrations.json`.

---

## Task Decorator Reference

```python
@task(
    name="task_name",          # Unique identifier, used to reference this task
    title="Task Title",        # Human readable title
    description="...",         # Optional description
    type="collector",          # "collector" or "insight"
    severity="high",           # "low", "medium", "high", "critical" (insights only)
    order=100,                 # Execution order (collectors default to 100, insights to 500)
    enabled=True              # Whether the task is enabled
)
```

---

## TaskContext Reference

Inside any task, `ctx` gives you access to the following:

```python
# Access setup data from StageOne (e.g. credentials)
ctx.base("api_key")

# Get data from another task
ctx.get_data("list_items")

# Check if an upstream task succeeded
ctx.succeeded("list_items")

# Get the message from another task
ctx.get_message("list_items")

# Add a log entry
ctx.add_log("Processing items...")

# Add an error
ctx.add_error("Something went wrong")

# Access the job config
ctx.config.get("some_config_value")
```

---

## Execution Order

1. **StageOne** runs first — authenticates and returns base context available to all tasks via `ctx.base()`
2. **Collectors** run next (order 100 by default) — gather data
3. **Insights** run last (order 500 by default) — analyze data and flag violations

---

## Example: Full Integration

For a complete working example, see `integrations/hello_world/`.