import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


class StateManager:
    """
    管理状态与历史记录，供 API 和前端读取。
    """

    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.status_file = self.state_dir / "status.json"
        self.history_file = self.state_dir / "history.jsonl"
        self.runtime_config_file = self.state_dir / "runtime-config.json"

    def save_status(self, data: Dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with open(self.status_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_status(self) -> Dict[str, Any]:
        if not self.status_file.exists():
            return {}
        with open(self.status_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def append_history(self, data: Dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def load_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        if not self.history_file.exists():
            return []
        with open(self.history_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        history = []
        for line in lines[-limit:]:
            try:
                history.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return history[::-1]  # 最新在前

    # -------- 运行时配置（启动前设定，停止后清空） --------
    def save_runtime_config(self, data: Dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with open(self.runtime_config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_runtime_config(self) -> Dict[str, Any]:
        if not self.runtime_config_file.exists():
            return {}
        with open(self.runtime_config_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def clear_runtime_config(self) -> None:
        if self.runtime_config_file.exists():
            self.runtime_config_file.unlink()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
