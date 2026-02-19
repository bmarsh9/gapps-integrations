import os
import pkgutil
import importlib
from utils.logger import logger


def register_tasks(runner_class):
    integration_name = runner_class.name

    for subfolder in ["collectors", "insights"]:
        task_path = os.path.join(
            os.path.dirname(__file__),  # /worker/utils
            "..",                        # /worker
            "integrations",              # /worker/integrations
            integration_name,            # /worker/integrations/hello_world
            subfolder                    # /worker/integrations/hello_world/collectors
        )
        task_path = os.path.abspath(task_path)

        if not os.path.isdir(task_path):
            logger.warning(f"No directory found for: {task_path}")
            continue

        for _, module_name, _ in pkgutil.iter_modules([task_path]):
            full_module = f"{module_name}"
            try:
                import importlib.util
                file_path = os.path.join(task_path, f"{module_name}.py")
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception as e:
                logger.error(f"Failed to import {module_name}: {e}")
                continue

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if callable(attr) and hasattr(attr, "_task_metadata"):
                    setattr(runner_class.StageTwo, attr.__name__, attr)