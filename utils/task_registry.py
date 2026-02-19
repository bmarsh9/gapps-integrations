import os
import pkgutil
import importlib
from utils.logger import logger


def register_tasks(runner_class):
    integration_name = runner_class.name
    integration_dir = os.path.dirname(runner_class.__module__.replace(".", "/"))

    for subfolder in ["collectors", "insights"]:
        task_type = subfolder
        task_path = os.path.join(os.path.dirname(__file__), "..", integration_dir, subfolder)
        task_path = os.path.abspath(task_path)
        package = f"integrations.{integration_name}.{subfolder}"

        if not os.path.isdir(task_path):
            logger.warning(f"No directory found for: {task_path}")
            continue

        for _, module_name, _ in pkgutil.iter_modules([task_path]):
            full_module = f"{package}.{module_name}"
            try:
                module = importlib.import_module(full_module)
            except Exception as e:
                logger.error(f"Failed to import {full_module}: {e}")
                continue

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if callable(attr) and hasattr(attr, "_task_metadata"):
                    setattr(runner_class.StageTwo, attr.__name__, attr)
