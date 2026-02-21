from utils.logger import logger
from utils.exceptions import TaskNotRun
from datetime import datetime
import concurrent.futures
from config import Config
import requests
from urllib.parse import urljoin
from utils.insight_registry import InsightControlRegistry
from utils.task_registry import register_tasks


class TaskContext:
    def __init__(self, base_context: dict = None, config: dict = None):
        self._context = base_context or {}
        self._results = {}
        self._raw_results = {}
        self._errors = {}
        self._traceback = {}
        self._logs = {}
        self.config = config or {}
        self.logger = logger
        self.registry = InsightControlRegistry()
        self._violations = {}  # Changed: per-task violation tracking
        self._status = {}
        self._start_times = {}
        self._end_times = {}
        self.store = {}

    def base(self, key: str, default=None):
        """
        Access a value from the base context (StageOne output).

        Args:
            key (str): The key to retrieve.
            default (any): The default value if key is not found.

        Returns:
            any: The value from the context or the default.
        """
        return self._context.get(key, default)

    def current_task_name(self) -> str:
        return getattr(self, "_current_task", "unknown")

    def _resolve_task_name(self, task_name):
        return task_name or getattr(self, "_current_task", "unknown")

    def get_status(self, task_name=None):
        task_name = self._resolve_task_name(task_name)
        return self._status.get(task_name, "queued")

    def get_raw_result(self, task_name=None):
        task_name = self._resolve_task_name(task_name)
        return self._raw_results.get(task_name, {})

    def set_result(self, result: dict, task_name=None, violation=None):
        task_name = self._resolve_task_name(task_name)
        self._raw_results[task_name] = result
        if isinstance(violation, bool):
            self.set_violation(violation, task_name=task_name)

    def get_result(self, task_name=None):
        """
        Get the complete task result including all metadata.

        Returns full output: {success, result, errors, logs, controls, ...}

        For most cases, use get_data() instead for cleaner access.
        """
        task_name = self._resolve_task_name(task_name)
        return self.format_result(task_name)

    def get_data(self, task_name=None):
        """
        Get just the 'data' dict from a task result.

        This is the most common use case - accessing the data returned by
        a collector or insight task.

        Returns:
            dict: The data dict from the task result

        Example:
            buckets = ctx.get_data("list_buckets").get("buckets", [])
        """
        task_name = self._resolve_task_name(task_name)
        result = self.format_result(task_name)
        return result.get("output", {}).get("data", {})

    def succeeded(self, task_name=None):
        """
        Check if a task completed successfully.

        Returns:
            bool: True if task succeeded, False otherwise

        Example:
            if not ctx.succeeded("list_buckets"):
                return {"violation": False, "data": {"error": "upstream failed"}}
        """
        task_name = self._resolve_task_name(task_name)
        result = self.format_result(task_name)
        return result.get("success", False)

    def get_message(self, task_name=None):
        """
        Get the message from a task result.

        Returns:
            str: The message, or None if not present

        Example:
            upstream_msg = ctx.get_message("list_buckets")
        """
        task_name = self._resolve_task_name(task_name)
        result = self.format_result(task_name)
        return result.get("output", {}).get("message")

    def has_result(self, task_name=None) -> bool:
        task_name = self._resolve_task_name(task_name)
        return task_name in self._results

    def add_error(self, error: str, task_name=None):
        task_name = self._resolve_task_name(task_name)
        self._errors.setdefault(task_name, []).append(error)

    def get_errors(self, task_name=None):
        task_name = self._resolve_task_name(task_name)
        return self._errors.get(task_name, [])

    def add_log(self, log: str, task_name=None):
        task_name = self._resolve_task_name(task_name)
        # Prepend timestamp to log message
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # Include milliseconds
        timestamped_log = f"[{timestamp}] {log}"
        self._logs.setdefault(task_name, []).append(timestamped_log)

    def get_logs(self, task_name=None):
        task_name = self._resolve_task_name(task_name)
        return self._logs.get(task_name, [])

    def set_traceback(self, traceback: str, task_name=None):
        task_name = self._resolve_task_name(task_name)
        self._traceback[task_name] = traceback

    def get_traceback(self, task_name=None):
        task_name = self._resolve_task_name(task_name)
        return self._traceback.get(task_name)

    def get_controls(self, task_name=None):
        task_name = self._resolve_task_name(task_name)
        return self.registry.get_controls(task_name)

    def set_violation(self, violation: bool, task_name=None):
        """Set violation status for a specific task."""
        task_name = self._resolve_task_name(task_name)
        self._violations[task_name] = violation

    def get_violation(self, task_name=None) -> bool:
        """Get violation status for a specific task."""
        task_name = self._resolve_task_name(task_name)
        return self._violations.get(task_name, False)

    def create_violation(self, payload=None, task_name=None):
        """
        Create a violation record on the server.

        Args:
            payload (dict): Optional additional data to include in the violation
            task_name (str): Task name (defaults to current task)

        Returns:
            dict: The created violation data from the server, or None if failed

        Raises:
            requests.exceptions.RequestException: If the API call fails
        """
        if payload is None:
            payload = {}

        task_name = self._resolve_task_name(task_name)

        output = self.get_result(task_name)["output"]
        controls = self.get_controls(task_name)

        # Get severity from task metadata
        task_metadata = self._get_task_metadata(task_name)
        severity = task_metadata.get("severity", "medium") if task_metadata else "medium"

        # Extract resource_id from data if available
        resource_id = None
        if isinstance(output, dict) and "data" in output:
            data = output["data"]
            # Try common patterns for resource identification
            if "public_buckets" in data and data["public_buckets"]:
                resource_id = ",".join([b.get("name", str(b)) for b in data["public_buckets"]])
            elif "unencrypted_buckets" in data and data["unencrypted_buckets"]:
                resource_id = ",".join([b.get("name", str(b)) for b in data["unencrypted_buckets"]])
            elif "affected_users" in data and data["affected_users"]:
                resource_id = ",".join(data["affected_users"])
            elif "resource_id" in data:
                resource_id = data["resource_id"]

        # Enrich the payload with comprehensive metadata
        # Only include fields that the model's create_violation() accepts
        enriched_payload = {
            "task_name": task_name,
            "control_references": controls,
            "output": output,
            "severity": severity,  # From task decorator metadata
            "description": None,  # Optional - can be overridden in payload
            "violation_type": None,  # Optional
            "environment": None,  # Optional
            "meta": {
                # Store extra fields in meta instead
                "integration": self.config.get("integration_name"),
                "job_id": self.config.get("job_id"),
                "resource_id": resource_id,
            },
            "timestamp": datetime.utcnow().isoformat(),  # Pass as datetime object, not ISO string
        }

        # Merge user-provided payload (allows override)
        enriched_payload.update(payload)

        try:
            r = requests.post(
                urljoin(Config.INTEGRATIONS_BASE_URL, f"/jobs/{self.config['job_id']}/violations"),
                json=enriched_payload,
                timeout=10  # Add timeout to prevent hanging
            )
            r.raise_for_status()  # Raise exception for 4xx/5xx status codes

            response_data = r.json()
            self.logger.info(f"[{task_name}] Violation created successfully (HTTP {r.status_code})")

            return response_data

        except requests.exceptions.Timeout:
            error_msg = f"Timeout creating violation for {task_name}"
            self.logger.error(error_msg)
            raise requests.exceptions.RequestException(error_msg)

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error creating violation for {task_name}: {e.response.status_code}"
            self.logger.error(f"{error_msg} - {e.response.text}")
            raise

        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to create violation for {task_name}: {str(e)}"
            self.logger.error(error_msg)
            raise

    def _get_task_metadata(self, task_name):
        """
        Helper to get task metadata from the task methods.
        Used to access severity and other decorator parameters.
        """
        # This would need to be populated during task execution
        # For now, return None - will be set by decorator
        return getattr(self, f"_task_metadata_{task_name}", None)

    def format_result(self, task_name=None):
        task_name = self._resolve_task_name(task_name)

        if task_name in self._results:
            success = self._results[task_name].get("success", True)
            task_type = self._results[task_name].get("type", "collector")
        else:
            success = True
            task_type = "collector"

        start_time = self._start_times.get(task_name)
        end_time = self._end_times.get(task_name)
        duration_seconds = None

        if isinstance(start_time, datetime) and isinstance(end_time, datetime):
            duration_seconds = round((end_time - start_time).total_seconds())

        # Get controls for this task
        controls = self.get_controls(task_name)

        return {
            "success": success,
            "output": self.get_raw_result(task_name),  # Changed: result → output
            "errors": self.get_errors(task_name),
            "traceback": self.get_traceback(task_name),
            "logs": self.get_logs(task_name),
            "is_violation": self.get_violation(task_name),
            "status": self.get_status(task_name),
            "type": task_type,
            "controls": controls,  # Add control mappings
            "start_time": str(start_time),
            "end_time": str(end_time),
            "duration": duration_seconds
        }


class ExecutionContext:
    def __init__(self, config):
        self.config = config
        self.data = {}
        self.start_time = datetime.utcnow()


class BaseRunner:
    name = "base"

    def __init__(self, config: dict):
        self.config = config
        config["integration_name"] = self.name  # set before stages are created
        register_tasks(self.__class__)
        self.context = ExecutionContext(config)
        self.stage_one = self.StageOne(config)
        self.stage_two = self.StageTwo(config)

    def run(self):
        self.context.data.update(self.stage_one.start())
        return self.stage_two.start(self.context.data)

    class StageOne:
        def __init__(self, config: dict):
            self.config = config

        def start(self) -> dict:
            return {}  # Default no-op, override in subclass

    class StageTwo:
        def __init__(self, config: dict):
            self.config = config

        def start(self, base_context: dict):
            requested_tasks = self.config.get("tasks", [])
            timeout = self.config.get("task_timeout", Config.TASK_TIMEOUT)

            ctx = TaskContext(base_context, config=self.config)

            task_methods = [
                getattr(self, name)
                for name in dir(self)
                if callable(getattr(self, name))
                   and hasattr(getattr(self, name), "_task_metadata")
                   and getattr(self, name)._task_metadata.get("enabled", True)
            ]

            task_methods.sort(key=lambda m: m._task_metadata.get("order", 100))

            for method in task_methods:
                task_name = method._task_metadata["name"]

                if requested_tasks and task_name not in requested_tasks:
                    continue

                try:
                    with concurrent.futures.ThreadPoolExecutor(
                            max_workers=1
                    ) as executor:

                        ctx.logger.info(f"[{task_name}] Executing task")
                        future = executor.submit(method, ctx)
                        task_output = future.result(timeout=timeout)
                        ctx.logger.info(f"[{task_name}] Task success:{task_output.get('success')}")

                except Exception as e:
                    """
                    We should really never hit this code b/c the task failure is handled
                    within the wrapped function described in decorators.py
                    """
                    ctx.logger.error(f"[Circuit catch][{task_name}] Error: {e}")
                    ctx.add_error(
                        f"Circuit catch. Error while trying to execute the task:{task_name}"
                    )
                    ctx.add_error(str(e))
                    result_data = ctx.format_result()
                    task_output = result_data["success"] = False
                ctx._results[task_name] = task_output
            return ctx._results