"""Phase 1: determine issue number, build analysis prompt, emit runtime paths."""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path


def determine_issue_number() -> str:
    event_name = os.environ["EVENT_NAME"]
    issue_number = os.environ.get("INPUT_ISSUE_NUMBER", "").strip()
    event = json.loads(
        Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8")
    )

    if not issue_number:
        if event_name in {"issues", "issue_comment"}:
            issue_number = str(event["issue"]["number"])
        elif event_name == "workflow_dispatch":
            issue_number = (
                str(event.get("inputs", {}).get("issue_number", "")).strip()
            )

    if not issue_number:
        raise SystemExit(
            "Unable to determine issue number. "
            "Pass input issue-number or expose workflow_dispatch input issue_number."
        )
    return issue_number


def build_prompt(issue_number: str) -> str:
    event_name = os.environ["EVENT_NAME"]
    bot_name = os.environ.get("BOT_NAME", "")
    answer_file = os.environ["ANSWER_FILE"]
    prompt_template = os.environ["PROMPT_TEMPLATE"]
    comment_prompt_template = os.environ["COMMENT_PROMPT_TEMPLATE"]
    repository = os.environ["REPOSITORY"]
    event = json.loads(
        Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8")
    )

    raw_comment = ""
    if event_name == "issue_comment":
        raw_comment = event.get("comment", {}).get("body", "")

    cleaned = raw_comment
    if bot_name:
        cleaned = re.sub(
            rf"{re.escape(bot_name)}\b", "", cleaned, flags=re.IGNORECASE
        )
    cleaned = re.sub(r"^[\s,，.。!！?？:：]+", "", cleaned).strip()

    def render(tpl: str) -> str:
        return (
            tpl.replace("{{issue_number}}", issue_number)
            .replace("{{answer_file}}", answer_file)
            .replace("{{comment_body}}", cleaned)
            .replace("{{repository}}", repository)
            .replace("{{event_name}}", event_name)
        )

    prompt = render(prompt_template).strip()
    extra = render(comment_prompt_template).strip() if cleaned else ""

    if extra:
        prompt = f"{prompt}\n\n{extra}" if prompt else extra

    return prompt


def write_output(fh, name: str, value: str) -> None:
    """Write a single- or multi-line value to GITHUB_OUTPUT."""
    if "\n" in value:
        delim = f"EOF_{uuid.uuid4().hex}"
        v = value if value.endswith("\n") else f"{value}\n"
        fh.write(f"{name}<<{delim}\n{v}{delim}\n")
    else:
        fh.write(f"{name}={value}\n")


def main() -> None:
    issue_number = determine_issue_number()
    prompt = build_prompt(issue_number)

    cache_dir = os.environ.get("CACHE_DIR", ".cache")
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)

    prompt_file = cache / "analysis_prompt.txt"
    prompt_file.write_text(f"{prompt}\n", encoding="utf-8")

    details_summary = os.environ.get("DETAILS_SUMMARY", "Details")
    action_link_text = os.environ.get("ACTION_LINK_TEXT", "GitHub Action run")
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repository = os.environ["REPOSITORY"]
    run_id = os.environ["GITHUB_RUN_ID"]

    action_link = (
        f"\U0001f517 [{action_link_text}]"
        f"({server_url}/{repository}/actions/runs/{run_id})"
    )
    details_begin = f"<details><summary>{details_summary}</summary>"

    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as fh:
        write_output(fh, "issue_number", issue_number)
        write_output(fh, "analysis_prompt_file", str(prompt_file))
        write_output(fh, "agent_output_file", str(cache / "agent_output.log"))
        write_output(fh, "agent_execution_log_file", str(cache / "agent_execution.log"))
        write_output(fh, "agent_output_artifact_file", str(cache / "agent_output.txt"))
        write_output(fh, "comment_body_file", str(cache / "comment_body.txt"))
        write_output(fh, "final_comment_file", str(cache / "final_comment.md"))
        write_output(fh, "final_conclusion_artifact_file", str(cache / "final_conclusion.md"))
        write_output(fh, "action_link", action_link)
        write_output(fh, "details_begin", details_begin)
        write_output(fh, "details_end", "</details>")

    print(f"Issue number: {issue_number}")
    print(f"Prompt written to: {prompt_file}")


if __name__ == "__main__":
    main()
