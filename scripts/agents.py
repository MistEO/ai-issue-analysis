"""Agent registry: install, configure, and build CLI commands for each supported AI agent."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class Agent:
    name: str
    display_name: str
    default_package: str
    default_model: str

    def install(self, package: str) -> None:
        pkg = package or self.default_package
        print(f"Installing {self.display_name} CLI: {pkg}")
        subprocess.check_call(
            ["npm", "install", "-g", pkg],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

    def resolve_model(self, model: str) -> str:
        return model or self.default_model

    def configure(self, api_key: str, base_url: str, model: str) -> dict[str, str]:
        """Return env vars to inject into the agent process."""
        raise NotImplementedError

    def build_command(self, model: str, prompt: str, extra_args: list[str]) -> list[str]:
        raise NotImplementedError

    def setup_skill_links(self) -> None:
        """Create cross-agent skill directory symlinks when needed."""
        pass


class Copilot(Agent):
    name = "copilot"
    display_name = "Copilot"
    default_package = "@github/copilot"
    default_model = "gpt-5.6-terra"

    def configure(self, api_key: str, base_url: str, model: str) -> dict[str, str]:
        return {"COPILOT_GITHUB_TOKEN": api_key}

    def build_command(self, model: str, prompt: str, extra_args: list[str]) -> list[str]:
        return [
            "copilot", "--yolo",
            "--model", self.resolve_model(model),
            *extra_args,
            "--prompt", prompt,
        ]


class Claude(Agent):
    name = "claude"
    display_name = "Claude"
    default_package = "@anthropic-ai/claude-code@2.1.220"
    default_model = "claude-sonnet-5"

    def configure(self, api_key: str, base_url: str, model: str) -> dict[str, str]:
        env: dict[str, str] = {"ANTHROPIC_API_KEY": api_key}
        if base_url:
            env["ANTHROPIC_BASE_URL"] = base_url
        return env

    def build_command(self, model: str, prompt: str, extra_args: list[str]) -> list[str]:
        return [
            "claude", "-p",
            "--model", self.resolve_model(model),
            "--dangerously-skip-permissions",
            *extra_args,
            prompt,
        ]

    def setup_skill_links(self) -> None:
        if Path(".codex").is_dir() and not Path(".claude").exists():
            os.symlink(".codex", ".claude")
            print("Linked .codex -> .claude")
        elif Path(".claude").is_dir():
            print(".claude already exists, skipping")
        else:
            print("No .claude or .codex directory found")


class Codex(Agent):
    name = "codex"
    display_name = "Codex"
    default_package = "@openai/codex"
    default_model = "gpt-5.6-terra"

    def configure(self, api_key: str, base_url: str, model: str) -> dict[str, str]:
        model = self.resolve_model(model)
        codex_home = Path.home() / ".codex"
        codex_home.mkdir(parents=True, exist_ok=True)
        config_path = codex_home / "config.toml"

        lines = [f'model = "{model}"']
        if base_url:
            lines += [
                'model_provider = "custom"',
                "",
                "[model_providers.custom]",
                'name = "Custom Provider"',
                f'base_url = "{base_url}"',
                'env_key = "CODEX_API_KEY"',
                'wire_api = "responses"',
                "supports_websockets = false",
                "requires_openai_auth = false",
            ]
        else:
            lines.append('openai_base_url = "https://api.openai.com/v1"')

        config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Codex config written to {config_path}:")
        print(config_path.read_text(encoding="utf-8"))

        return {"CODEX_API_KEY": api_key}

    def build_command(self, model: str, prompt: str, extra_args: list[str]) -> list[str]:
        return [
            "codex", "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            *extra_args,
            prompt,
        ]

    def setup_skill_links(self) -> None:
        if Path(".claude").is_dir() and not Path(".codex").exists():
            os.symlink(".claude", ".codex")
            print("Linked .claude -> .codex")
        elif Path(".codex").is_dir():
            print(".codex already exists, skipping")
        else:
            print("No .claude or .codex directory found")


_REGISTRY: dict[str, Agent] = {
    "copilot": Copilot(),
    "claude": Claude(),
    "codex": Codex(),
}


def get_agent(name: str) -> Agent:
    agent = _REGISTRY.get(name.lower())
    if agent is None:
        supported = ", ".join(sorted(_REGISTRY))
        raise SystemExit(f"Unknown agent: {name!r}. Supported: {supported}")
    return agent


def list_agents() -> list[str]:
    return sorted(_REGISTRY)
