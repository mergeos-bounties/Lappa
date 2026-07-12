import os
from pathlib import Path

class WorkspaceManager:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path).resolve()

    def register_external_path(self, external_path: str) -> dict:
        \"\"\"
        Registra una ruta externa de forma segura, validando que no escape del sandbox.
        \"\"\"
        target_path = Path(external_path).resolve()

        try:
            target_path.relative_to(self.base_path)
        except ValueError:
            raise ValueError(f"Path escape blocked: {external_path} is outside the workspace")

        return {
            "status": "success",
            "path": str(target_path),
            "message": "External path registered successfully"
        }
