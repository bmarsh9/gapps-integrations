from functools import wraps
from config import Config
import traceback
from datetime import datetime


def task(name, title, description=None, enabled=True, type="collector", order=None, severity=None, depends_on=None):
    """
    Task decorator with dependency tracking.

    Args:
        name (str): Unique task identifier
        title (str): Human-readable title
        description (str): Task description
        enabled (bool): Whether task is enabled
        type (str): "collector" or "insight"
        order (int): Execution order (collectors default to 100, insights to 500)
        severity (str): Severity level for insight tasks ("low", "medium", "high", "critical")
        depends_on (list): List of task names this task depends on
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, ctx: "TaskContext", *args, **kwargs):
            ctx._current_task = name
            ctx._status[name] = "in_progress"
            ctx._start_times[name] = datetime.utcnow()

            # Store task metadata in context for access by create_violation
            setattr(ctx, f"_task_metadata_{name}", wrapper._task_metadata)

            # NEW: Check dependencies before executing
            dependencies = depends_on or []
            for dep_task in dependencies:
                # Check if dependency was executed
                if not ctx.has_result(dep_task):
                    error_msg = f"Dependency '{dep_task}' was not executed"
                    ctx.logger.error(f"[{name}] {error_msg}")
                    ctx.add_error(error_msg)
                    ctx._status[name] = "skipped"
                    ctx._end_times[name] = datetime.utcnow()

                    result_data = ctx.format_result(name)
                    result_data["success"] = False
                    result_data["type"] = type
                    ctx._results[name] = result_data
                    return result_data

                # Check if dependency succeeded
                dep_result = ctx.get_result(dep_task)
                if not dep_result.get("success"):
                    error_msg = f"Dependency '{dep_task}' failed - skipping task"
                    ctx.logger.warning(f"[{name}] {error_msg}")
                    ctx.add_error(error_msg)
                    ctx._status[name] = "skipped"
                    ctx._end_times[name] = datetime.utcnow()

                    result_data = ctx.format_result(name)
                    result_data["success"] = False
                    result_data["type"] = type
                    ctx._results[name] = result_data
                    return result_data

            try:
                task_return_value = func(self, ctx, *args, **kwargs)

                # Validate return value structure
                if not isinstance(task_return_value, dict):
                    raise ValueError(
                        f"Task must return a dict, got {type(task_return_value).__name__}"
                    )

                # Required key: 'data' must be present and must be a dict
                if "data" not in task_return_value:
                    raise ValueError(
                        f"Task return must include 'data' key"
                    )

                if not isinstance(task_return_value.get("data"), (dict, list)):
                    raise ValueError(
                        f"'data' must be a dict or list"
                    )

                # Optional key: 'violation' must be a bool if present (defaults to False)
                violation = task_return_value.get("violation", False)
                if not isinstance(violation, bool):
                    raise ValueError(
                        f"'violation' must be a bool, got {type(violation).__name__}"
                    )

                # Optional key: 'message' must be a str if present
                message = task_return_value.get("message")
                if message is not None and not isinstance(message, str):
                    raise ValueError(
                        f"'message' must be a str, got {type(message).__name__}"
                    )

                # Warn about unexpected keys
                expected_keys = {"data", "violation", "message"}
                unexpected_keys = set(task_return_value.keys()) - expected_keys
                if unexpected_keys:
                    ctx.logger.warning(
                        f"[{name}] Unexpected keys in return value: {unexpected_keys}. "
                        f"Expected keys: {expected_keys}"
                    )

                # Extract violation flag (remove from dict for storage)
                violation_flag = task_return_value.pop("violation", False)

                # Store the rest as the result (data and message)
                ctx.set_result(task_return_value, violation=violation_flag)

                # Task succeeded if it returned valid structure
                success = True

            except Exception as e:
                success = False
                tb = traceback.format_exc()
                if Config.DEBUG:
                    ctx.logger.error(tb)
                else:
                    ctx.logger.error(str(e))
                ctx.add_error(str(e))
                ctx.set_traceback(tb)

            ctx._status[name] = "done"
            ctx._end_times[name] = datetime.utcnow()

            # Auto-create violation for insight tasks that have violations
            if type == "insight" and success and ctx.get_violation(name):
                try:
                    ctx.logger.info(f"[{name}] Auto-creating violation")
                    ctx.create_violation(task_name=name)
                except Exception as e:
                    ctx.logger.error(f"[{name}] Failed to create violation: {e}")
                    # Don't fail the task if violation creation fails
                    ctx.add_error(f"Failed to create violation: {str(e)}")

            # Set final formatted result using centralized formatter
            result_data = ctx.format_result(name)
            result_data["success"] = success
            result_data["type"] = type  # enforce explicit type
            ctx._results[name] = result_data
            return result_data

        wrapper._task_metadata = {
            "name": name,
            "title": title,
            "description": description,
            "enabled": enabled,
            "type": type,
            "order": order if order is not None else (500 if type == "insight" else 100),
            "severity": severity,  # Store severity in metadata
            "depends_on": depends_on or []  # Store dependencies in metadata
        }
        return wrapper

    return decorator