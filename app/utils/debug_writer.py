import os
import uuid
from datetime import datetime
from typing import Optional, Any
from pathlib import Path


class DebugWriter:
    """
    Optional debug logging service that writes each pipeline step to markdown files.
    Enabled via DEBUG_MODE=true in .env
    """

    _enabled: Optional[bool] = None
    _output_dir: Optional[Path] = None

    @classmethod
    def _is_enabled(cls) -> bool:
        if cls._enabled is None:
            cls._enabled = os.getenv("DEBUG_MODE", "false").lower() == "true"
        return cls._enabled

    @classmethod
    def _get_output_dir(cls) -> Path:
        if cls._output_dir is None:
            output_path = os.getenv("DEBUG_OUTPUT_DIR", "debug_output")
            cls._output_dir = Path(output_path)
            cls._output_dir.mkdir(parents=True, exist_ok=True)
        return cls._output_dir

    @classmethod
    def _get_run_dir(cls) -> Path:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]
        run_dir = cls._get_output_dir() / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    @classmethod
    def start_run(cls) -> Optional[Path]:
        """Start a new debug run and return the run directory path."""
        if not cls._is_enabled():
            return None
        return cls._get_run_dir()

    @classmethod
    def write_step(
        cls,
        run_dir: Optional[Path],
        step_name: str,
        step_number: int,
        title: str,
        input_data: Optional[dict] = None,
        output_data: Optional[Any] = None,
        prompt: Optional[str] = None,
        api_request: Optional[dict] = None,
        api_response: Optional[Any] = None,
        notes: Optional[str] = None,
    ) -> Optional[Path]:
        """Write a single step to a markdown file."""
        if run_dir is None or not cls._is_enabled():
            return None

        filename = f"step_{step_number:02d}_{step_name}.md"
        filepath = run_dir / filename

        lines = [
            f"# Step {step_number}: {title}",
            "",
            f"**Step Name:** {step_name}",
            f"**Timestamp:** {datetime.now().isoformat()}",
            "",
        ]

        if notes:
            lines.extend(["## Notes", f"{notes}", ""])

        if prompt:
            lines.extend(["## Prompt Sent to LLM", "```markdown", prompt, "```", ""])

        if api_request:
            lines.extend(["## API Request", "```json", cls._format_json(api_request), "```", ""])

        if input_data:
            lines.extend(["## Input Data", "```json", cls._format_json(input_data), "```", ""])

        if api_response is not None:
            lines.extend(["## API Response", "```json", cls._format_output(api_response), "```", ""])

        if output_data is not None:
            lines.extend(["## Output / Parsed Result", "```json", cls._format_output(output_data), "```", ""])

        filepath.write_text("\n".join(lines))
        return filepath

    @classmethod
    def write_summary(
        cls,
        run_dir: Optional[Path],
        total_steps: int,
        execution_time: float,
        final_result: Optional[Any] = None,
        errors: Optional[list] = None,
    ) -> Optional[Path]:
        """Write a summary markdown file for the entire run."""
        if run_dir is None or not cls._is_enabled():
            return None

        filepath = run_dir / "summary.md"

        lines = [
            "# Debug Run Summary",
            "",
            f"**Total Steps:** {total_steps}",
            f"**Execution Time:** {execution_time:.2f}s",
            f"**Timestamp:** {datetime.now().isoformat()}",
            "",
            "## Steps Executed",
        ]

        for i in range(1, total_steps + 1):
            lines.append(f"- Step {i}: See step_{i:02d}_*.md")

        if errors:
            lines.extend(["", "## Errors", "```", "\n".join(str(e) for e in errors), "```", ""])

        if final_result:
            lines.extend(["", "## Final Result", "```json", cls._format_output(final_result), "```", ""])

        filepath.write_text("\n".join(lines))
        return filepath

    @classmethod
    def _format_json(cls, data: dict) -> str:
        """Format a dict as pretty JSON string."""
        import json
        try:
            return json.dumps(data, indent=2, default=str)
        except Exception:
            return str(data)

    @classmethod
    def _format_output(cls, data: Any) -> str:
        """Format output data as string."""
        if hasattr(data, "model_dump_json"):
            return data.model_dump_json(indent=2)
        elif hasattr(data, "model_dump"):
            return cls._format_json(data.model_dump())
        elif hasattr(data, "dict"):
            return cls._format_json(data.dict())
        else:
            try:
                import json
                return json.dumps(data, indent=2, default=str)
            except Exception:
                return str(data)
