"""Offline regression tests for issue comments and retained execution artifacts."""

from __future__ import annotations

import contextlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import finalize
import run_agent


ACTION_LINK = "[Run](https://github.com/example/repo/actions/runs/1)"
DETAILS_BEGIN = "<details><summary>Execution log</summary>"
RAW_LOG = (
    "PRIVATE_EXECUTION_SENTINEL\nexec\ncat SKILL.md\n"
    "```markdown\n# Tool output\n```\n</details>\n"
    "<details open><summary>Injected</summary>\n"
    "<script>alert('not executable')</script>\n"
    "</details>\nLATEST_PROGRESS_SENTINEL\n"
)
ANSWER = "# Conclusion\n\nThe result.\n\n<details><summary>English</summary>\n\nTranslation.\n</details>\n"


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.starts = []
        self.ends = []
        self.data = []

    def handle_starttag(self, tag, attrs):
        self.starts.append(tag)

    def handle_endtag(self, tag):
        self.ends.append(tag)

    def handle_data(self, text):
        self.data.append(text)


class CommentOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {
            "COMMENT_ID": "123",
            "ISSUE_NUMBER": "6469",
            "REPOSITORY": "example/repo",
            "REPO": "example/repo",
            "GITHUB_SERVER_URL": "https://github.com",
            "ACTION_LINK": ACTION_LINK,
            "DETAILS_BEGIN": DETAILS_BEGIN,
            "DETAILS_END": "</details>",
            "EXTRA_COMMENT_CONTENT": "Footer",
            "RESULT_ERROR_MESSAGE": "Analysis failed. See the run log.",
            "PROCESS_ERROR_MESSAGE": "No answer was produced.",
            "AGENT_NAME": "codex",
            "API_KEY": "test-only-key",
            "COMMENT_GITHUB_TOKEN": "test-only-token",
            "INITIAL_BODY": "Analysis in progress.",
            "STREAM_UPDATE_INTERVAL": "1",
        }
        for name in [
            "ANALYSIS_PROMPT_FILE", "EXECUTION_LOG_FILE", "OUTPUT_ARTIFACT_FILE",
            "ANSWER_FILE", "CONCLUSION_ARTIFACT_FILE", "OUTPUT_FILE",
            "FINAL_COMMENT_FILE", "GITHUB_OUTPUT", "BODY_FILE",
        ]:
            self.env[name] = str(self.root / name.lower())
        self.write("ANALYSIS_PROMPT_FILE", "Analyze the issue.")
        self.write("OUTPUT_FILE", RAW_LOG)
        self.write("EXECUTION_LOG_FILE", "Invocation header\n" + RAW_LOG)
        self.write("ANSWER_FILE", ANSWER)

    def write(self, name, value):
        Path(self.env[name]).write_text(value, encoding="utf-8")

    def read(self, name):
        return Path(self.env[name]).read_text(encoding="utf-8")

    def finish(self):
        with patch.dict(os.environ, self.env, clear=True), contextlib.redirect_stdout(io.StringIO()):
            finalize.main()
        return self.read("FINAL_COMMENT_FILE")

    def run_fake_agent(self, *, exit_code=0):
        agent = Mock(display_name="Fake agent")
        agent.resolve_model.return_value = "test-model"
        agent.configure.return_value = {}
        agent.build_command.return_value = ["fake-agent", "--prompt", "test"]
        proc = Mock(pid=123, returncode=exit_code)
        # Exercise both an in-progress update and the final flush without sleeps.
        proc.poll.side_effect = [None, None, exit_code, exit_code]
        proc.wait.return_value = exit_code

        def start(*args, **kwargs):
            kwargs["stdout"].write(RAW_LOG)
            kwargs["stdout"].flush()
            return proc

        with (
            patch.dict(os.environ, self.env, clear=True),
            patch.object(run_agent, "get_agent", return_value=agent),
            patch.object(run_agent.subprocess, "Popen", side_effect=start),
            patch.object(run_agent.time, "sleep"),
            patch.object(run_agent, "update_comment") as publish,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            with self.assertRaises(SystemExit) as ended:
                run_agent.main()
            self.assertEqual(ended.exception.code, exit_code)
        return publish

    def test_final_comment_defaults_to_conclusion_only(self):
        body = self.finish()
        self.assertEqual(body, ANSWER.rstrip("\n") + "\n\n---\n\n" + ACTION_LINK + "\n\nFooter\n")
        self.assertNotIn("PRIVATE_EXECUTION_SENTINEL", body)
        self.assertNotIn(DETAILS_BEGIN, body)
        self.assertEqual(self.read("OUTPUT_ARTIFACT_FILE"), "Invocation header\n" + RAW_LOG)
        self.assertEqual(self.read("CONCLUSION_ARTIFACT_FILE"), ANSWER)
        self.assertIn("PRIVATE_EXECUTION_SENTINEL", self.read("GITHUB_OUTPUT"))

    def test_explicit_false_does_not_publish_logs(self):
        self.env["PUBLISH_EXECUTION_LOG"] = "false"
        self.assertNotIn("PRIVATE_EXECUTION_SENTINEL", self.finish())
        self.run_fake_agent().assert_not_called()

    def test_missing_answer_publishes_error_without_logs(self):
        Path(self.env["ANSWER_FILE"]).unlink()
        body = self.finish()
        self.assertTrue(body.startswith(self.env["RESULT_ERROR_MESSAGE"]))
        self.assertNotIn("PRIVATE_EXECUTION_SENTINEL", body)
        self.assertIn(ACTION_LINK, body)
        self.assertIn("Answer file not found", self.read("CONCLUSION_ARTIFACT_FILE"))

    def test_empty_answer_publishes_error_without_logs(self):
        for value in ["", " \n\t\n"]:
            with self.subTest(answer=repr(value)):
                self.write("ANSWER_FILE", value)
                body = self.finish()
                self.assertTrue(body.startswith(self.env["RESULT_ERROR_MESSAGE"]))
                self.assertNotIn("PRIVATE_EXECUTION_SENTINEL", body)

    def test_running_agent_does_not_publish_logs_by_default(self):
        self.run_fake_agent().assert_not_called()
        self.assertIn(RAW_LOG, self.read("EXECUTION_LOG_FILE"))
        self.assertIn("exit code: 0", self.read("EXECUTION_LOG_FILE"))
        self.assertFalse(Path(self.env["BODY_FILE"]).exists())

    def test_failed_agent_keeps_log_without_publishing_it(self):
        self.run_fake_agent(exit_code=1).assert_not_called()
        self.assertIn(RAW_LOG, self.read("EXECUTION_LOG_FILE"))
        self.assertIn("exit code: 1", self.read("EXECUTION_LOG_FILE"))

    def assert_safe_debug_log(self, body, expected_details):
        parsed = Markup()
        parsed.feed(body)
        self.assertEqual(parsed.starts.count("details"), expected_details)
        self.assertEqual(parsed.ends.count("details"), expected_details)
        self.assertNotIn("script", parsed.starts)
        self.assertIn("&lt;/details&gt;", body)
        self.assertIn("PRIVATE_EXECUTION_SENTINEL", "".join(parsed.data))
        self.assertIn(ACTION_LINK, body)

    def test_explicit_debug_mode_escapes_final_log(self):
        self.env["PUBLISH_EXECUTION_LOG"] = "true"
        body = self.finish()
        # One details block belongs to the answer, the other to the debug log.
        self.assert_safe_debug_log(body, expected_details=2)
        self.assertIn(ANSWER.rstrip("\n"), body)

    def test_explicit_debug_mode_escapes_streamed_log(self):
        self.env["PUBLISH_EXECUTION_LOG"] = "true"
        publish = self.run_fake_agent()
        self.assertGreaterEqual(publish.call_count, 1)
        self.assert_safe_debug_log(self.read("BODY_FILE"), expected_details=1)

    def test_large_debug_log_keeps_latest_progress_within_comment_budget(self):
        self.env["PUBLISH_EXECUTION_LOG"] = "true"
        raw = "<>&\"'" * 40000 + "LATEST_PROGRESS_SENTINEL"
        self.write("OUTPUT_FILE", raw)
        self.write("EXECUTION_LOG_FILE", raw)
        body = self.finish()
        self.assertLessEqual(len(body), 60000)
        self.assertIn("LATEST_PROGRESS_SENTINEL", body)
        self.assertIn("truncated", body.lower())
        self.assertIn(ANSWER.rstrip("\n"), body)
        self.assertEqual(self.read("OUTPUT_ARTIFACT_FILE"), raw)

    def test_oversized_conclusion_uses_artifact_notice(self):
        answer = "# Conclusion\n" + "Result. " * 10000
        self.write("ANSWER_FILE", answer)
        body = self.finish()
        self.assertLessEqual(len(body), 60000)
        self.assertIn("artifact", body.lower())
        self.assertIn(ACTION_LINK, body)
        self.assertEqual(self.read("CONCLUSION_ARTIFACT_FILE"), answer)

    def test_large_comment_update_uses_http_body_not_command_arguments(self):
        body = "中文" * 30000
        self.write("BODY_FILE", body)
        with patch.object(run_agent.urllib.request, "urlopen") as send:
            run_agent.update_comment(self.env["BODY_FILE"], "example/repo", "123", "test-only-token")
        request = send.call_args.args[0]
        self.assertEqual(request.get_method(), "PATCH")
        self.assertGreater(len(request.data), 128 * 1024)
        self.assertEqual(json.loads(request.data), {"body": body})
        self.assertEqual(send.call_args.kwargs["timeout"], 60)

    def test_action_declares_safe_default_and_wires_both_phases(self):
        action = (SCRIPTS.parent / "action.yml").read_text(encoding="utf-8")
        self.assertRegex(action, r'(?s)\n  publish-execution-log:\n.*?default: "false"')
        self.assertEqual(action.count("PUBLISH_EXECUTION_LOG: ${{ inputs.publish-execution-log }}"), 2)


if __name__ == "__main__":
    unittest.main()
