import json
from pathlib import Path

class InsightControlRegistry:
    def __init__(self, relative_path: str = "../control_to_insight_map.json"):
        base_dir = Path(__file__).parent.resolve()
        full_path = (base_dir / relative_path).resolve()
        self._framework_map = self._load(full_path)
        self._insight_to_controls = self._invert(self._framework_map)

    def _load(self, path: Path):
        with open(path, "r") as f:
            return json.load(f)

    def _invert(self, framework_map: dict):
        result = {}
        for framework, controls in framework_map.items():
            for control_id, insights in controls.items():
                for insight in insights:
                    result.setdefault(insight, []).append({
                        "framework": framework,
                        "control_id": control_id
                    })
        return result

    def get_controls(self, task_name: str):
        return self._insight_to_controls.get(task_name, [])
