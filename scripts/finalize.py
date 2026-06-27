"""Phase 3: build final comment, export action outputs, write artifact files."""

from __future__ import annotations

import os
import uuid
from pathlib import Path


def read_or(path: Path, fallback: str) -> str:
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return f"{fallback}\n"


def truncate(value: str, label: str, max_bytes: int = 300_000) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    suffix = (
        f"\n\n[Truncated {label} for GitHub Actions output size limits. "
        "Use the uploaded artifact for the full content.]\n"
    )
    trimmed = encoded[: max_bytes - len(suffix.encode("utf-8"))].decode(
        "utf-8", errors="ignore"
    )
    return f"{trimmed}{suffix}"


def write_output(fh, name: str, value: str) -> None:
    delim = f"EOF_{uuid.uuid4().hex}"
    v = value if value.endswith("\n") else f"{value}\n"
    fh.write(f"{name}<<{delim}\n{v}{delim}\n")


def main() -> None:
    comment_id = os.environ.get("COMMENT_ID", "")
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    issue_number = os.environ["ISSUE_NUMBER"]
    repository = os.environ["REPOSITORY"]

    prompt_file = Path(os.environ["ANALYSIS_PROMPT_FILE"])
    exec_log_file = Path(os.environ["EXECUTION_LOG_FILE"])
    output_artifact = Path(os.environ["OUTPUT_ARTIFACT_FILE"])
    answer_file = Path(os.environ["ANSWER_FILE"])
    conclusion_artifact = Path(os.environ["CONCLUSION_ARTIFACT_FILE"])
    output_file = Path(os.environ["OUTPUT_FILE"])
    final_comment_file = Path(os.environ["FINAL_COMMENT_FILE"])

    action_link = os.environ["ACTION_LINK"]
    details_begin = os.environ["DETAILS_BEGIN"]
    details_end = os.environ["DETAILS_END"]
    extra_content = os.environ.get("EXTRA_COMMENT_CONTENT", "")
    result_error = os.environ.get("RESULT_ERROR_MESSAGE", "Analysis error.")

    comment_url = (
        f"{server_url}/{repository}/issues/{issue_number}#issuecomment-{comment_id}"
        if comment_id
        else ""
    )

    # --- build final comment ---
    conclusion = read_or(answer_file, result_error).rstrip("\n")
    raw_output = read_or(output_file, "No agent output captured.")

    truncated_output = raw_output
    if len(truncated_output) > 55000:
        truncated_output = truncated_output[:55000] + "\n\n[truncated for comment size limit]"

    parts = [conclusion, "", "---", "", details_begin, "", "```text", truncated_output, "```", "", details_end, "", action_link]
    if extra_content:
        parts += ["", extra_content]
    final_comment_file.write_text("\n".join(parts) + "\n", encoding="utf-8")

    # --- write artifact files ---
    exec_log = read_or(exec_log_file, f"Execution log not found: {exec_log_file}")
    analysis_prompt = read_or(prompt_file, f"Prompt file not found: {prompt_file}")
    final_conclusion = read_or(answer_file, f"Answer file not found: {answer_file}")

    output_artifact.write_text(exec_log, encoding="utf-8")
    conclusion_artifact.write_text(final_conclusion, encoding="utf-8")

    # --- full analysis to stdout ---
    print(exec_log)
    print("\n---\n")
    if answer_file.is_file():
        print(answer_file.read_text(encoding="utf-8"))
    else:
        print(os.environ.get("PROCESS_ERROR_MESSAGE", "Analysis error."))

    # --- GITHUB_OUTPUT ---
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as fh:
        fh.write(f"comment-id={comment_id}\n")
        fh.write(f"comment-url={comment_url}\n")
        write_output(fh, "analysis-prompt", truncate(analysis_prompt, "analysis-prompt"))
        write_output(fh, "agent-output", truncate(exec_log, "agent-output"))
        write_output(fh, "final-conclusion", truncate(final_conclusion, "final-conclusion"))


if __name__ == "__main__":
    main()
