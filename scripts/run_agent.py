"""Phase 2: install CLI, configure agent, run with streaming comment updates."""

from __future__ import annotations

import json
import os
import secrets
import shlex
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agents import get_agent


def select_api_key(raw: str) -> tuple[str, int]:
    keys = [l.strip() for l in raw.splitlines() if l.strip()]
    if not keys:
        raise SystemExit("Input api-key is empty after trimming blank lines.")
    return secrets.choice(keys), len(keys)


def update_comment(body_file: str, repo: str, comment_id: str, token: str) -> None:
    body = Path(body_file).read_text(encoding="utf-8")
    subprocess.run(
        [
            "curl", "-s", "-L", "-X", "PATCH",
            "-H", f"Authorization: token {token}",
            "-H", "Accept: application/vnd.github.v3+json",
            f"https://api.github.com/repos/{repo}/issues/comments/{comment_id}",
            "-d", json.dumps({"body": body}),
        ],
        check=False,
        capture_output=True,
    )


def build_streaming_body(
    content: str,
    initial_body: str,
    details_begin: str,
    details_end: str,
    action_link: str,
    extra: str,
    max_len: int = 55000,
) -> str:
    if len(content) > max_len:
        content = content[:max_len] + "\n\n[truncated for comment size limit]"

    parts = [
        initial_body, "",
        "---", "",
        details_begin, "",
        "```text",
        content,
        "```", "",
        details_end, "",
        action_link,
    ]
    if extra:
        parts += ["", extra]
    return "\n".join(parts)


def main() -> None:
    agent_name = os.environ["AGENT_NAME"]
    api_key_raw = os.environ["API_KEY"]
    base_url = os.environ.get("API_BASE_URL", "").strip()
    model = os.environ.get("MODEL", "").strip()
    package = os.environ.get("AGENT_PACKAGE", "").strip()
    extra_args_raw = os.environ.get("AGENT_EXTRA_ARGS", "").strip()

    github_token = os.environ["COMMENT_GITHUB_TOKEN"]
    repo = os.environ["REPO"]
    comment_id = os.environ["COMMENT_ID"]
    issue_number = os.environ["ISSUE_NUMBER"]
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")

    prompt_file = os.environ["ANALYSIS_PROMPT_FILE"]
    output_file = os.environ["OUTPUT_FILE"]
    exec_log_file = os.environ["EXECUTION_LOG_FILE"]
    body_file = os.environ["BODY_FILE"]

    initial_body = os.environ["INITIAL_BODY"]
    action_link = os.environ["ACTION_LINK"]
    details_begin = os.environ["DETAILS_BEGIN"]
    details_end = os.environ["DETAILS_END"]
    interval = int(os.environ.get("STREAM_UPDATE_INTERVAL", "30"))
    extra_content = os.environ.get("EXTRA_COMMENT_CONTENT", "")

    agent = get_agent(agent_name)
    api_key, key_count = select_api_key(api_key_raw)

    agent.install(package)
    agent.setup_skill_links()

    model = agent.resolve_model(model)
    agent_env = agent.configure(api_key, base_url, model)

    prompt = Path(prompt_file).read_text(encoding="utf-8").strip()
    extra_args = shlex.split(extra_args_raw) if extra_args_raw else []
    cmd = agent.build_command(model, prompt, extra_args)

    comment_url = (
        f"{server_url}/{repo}/issues/{issue_number}#issuecomment-{comment_id}"
    )

    # --- execution log header ---
    safe_cmd_preview = " ".join(cmd[:4]) + " ... (prompt omitted)"
    header_lines = [
        f"{agent.display_name} invocation parameters:",
        f"  repo: {repo}",
        f"  issue-number: {issue_number}",
        f"  comment-id: {comment_id}",
        f"  comment-url: {comment_url}",
        f"  model: {model}",
        f"  api-key-count: {key_count}",
        f"  stream-update-interval-seconds: {interval}",
        f"  analysis-prompt-file: {prompt_file}",
        f"  output-file: {output_file}",
        f"  command: {safe_cmd_preview}",
        "Prompt content begins",
        prompt,
        "Prompt content ends",
    ]
    header = "\n".join(header_lines) + "\n"
    Path(exec_log_file).write_text(header, encoding="utf-8")
    print(header, end="")

    # --- launch agent ---
    Path(output_file).write_text("", encoding="utf-8")
    run_env = {**os.environ, **agent_env}

    output_fh = open(output_file, "w", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=output_fh,
            stderr=subprocess.STDOUT,
            env=run_env,
        )
    except Exception:
        output_fh.close()
        raise

    print(f"{agent.display_name} started with PID {proc.pid}")

    # --- streaming loop ---
    last_content = ""

    def _try_update() -> None:
        nonlocal last_content
        if not Path(output_file).is_file():
            return
        current = Path(output_file).read_text(encoding="utf-8")
        if current == last_content or not current:
            return
        body = build_streaming_body(
            current, initial_body, details_begin, details_end,
            action_link, extra_content,
        )
        Path(body_file).write_text(body, encoding="utf-8")
        update_comment(body_file, repo, comment_id, github_token)
        last_content = current
        print(f"Comment updated at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        while proc.poll() is None:
            elapsed = 0
            while elapsed < interval and proc.poll() is None:
                time.sleep(1)
                elapsed += 1
            _try_update()

        _try_update()
    finally:
        proc.wait()
        output_fh.close()

    exit_code = proc.returncode

    # --- append output to execution log ---
    agent_out = (
        Path(output_file).read_text(encoding="utf-8")
        if Path(output_file).is_file()
        else ""
    )
    with open(exec_log_file, "a", encoding="utf-8") as fh:
        fh.write(f"\n{agent.display_name} output begins\n")
        fh.write(agent_out)
        fh.write(f"\n{agent.display_name} output ends\n")
        fh.write(f"{agent.display_name} exit code: {exit_code}\n")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
