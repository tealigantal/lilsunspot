from __future__ import annotations

import asyncio


LOCAL_PROVIDER = {
    "id": "ollama",
    "type": "local",
    "env_key": "OLLAMA_API_KEY",
    "base_url": "http://127.0.0.1:11434/v1",
    "hermes_provider": "custom",
}


class FakeSessionDB:
    def get_messages_as_conversation(self, _session_id, include_ancestors=False):
        return []


class CapturingAgent:
    calls: list[dict] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.model = kwargs["model"]
        self.provider = kwargs["provider"]

    def run_conversation(self, user_message, conversation_history=None, task_id=None):
        self.calls.append(self.kwargs)
        return {
            "final_response": f"reply:{user_message}",
            "messages": [],
            "api_calls": 1,
            "model": self.model,
            "provider": self.provider,
        }


def _install_agent(daemon_client, monkeypatch, agent_class=CapturingAgent):
    agent_class.calls = []
    monkeypatch.setattr(daemon_client.agent_runner, "_load_hermes_classes", lambda _paths: (agent_class, FakeSessionDB))


def _save_local_provider(daemon_client):
    daemon_client.hermes_runtime.save_provider_credentials(
        LOCAL_PROVIDER,
        "llama3.2",
        "",
        paths=daemon_client.config_paths.get_runtime_paths(),
    )


def test_generation_modes_change_real_agent_request_parameters(daemon_client, monkeypatch):
    _install_agent(daemon_client, monkeypatch)
    _save_local_provider(daemon_client)
    paths = daemon_client.config_paths.get_runtime_paths()
    conversation = daemon_client.conversations.create_conversation(title="真实生成参数", paths=paths)

    daemon_client.generation_controls.save_generation_selection(
        paths,
        scope="conversation",
        conversation_id=conversation["id"],
        selection={"mode": "strict"},
    )
    asyncio.run(daemon_client.agent_runner.send_agent_message("严谨回答", conversation["id"], paths))
    strict = CapturingAgent.calls[-1]

    daemon_client.generation_controls.save_generation_selection(
        paths,
        scope="conversation",
        conversation_id=conversation["id"],
        selection={"mode": "creative"},
    )
    asyncio.run(daemon_client.agent_runner.send_agent_message("创意回答", conversation["id"], paths))
    creative = CapturingAgent.calls[-1]

    assert strict["max_tokens"] == 1800
    assert strict["max_iterations"] == 40
    assert strict["reasoning_config"] == {"enabled": True, "effort": "high"}
    assert strict["request_overrides"] == {"temperature": 0.2, "seed": 0}
    assert creative["max_tokens"] == 1600
    assert creative["max_iterations"] == 24
    assert creative["request_overrides"] == {"temperature": 1.0, "top_p": 0.95}


def test_global_conversation_and_turn_priority_is_field_aware(daemon_client):
    _save_local_provider(daemon_client)
    paths = daemon_client.config_paths.get_runtime_paths()
    conversation = daemon_client.conversations.create_conversation(title="作用域", paths=paths)

    daemon_client.generation_controls.save_generation_selection(
        paths,
        scope="global",
        selection={"mode": "strict", "parameters": {"temperature": 0.15}},
    )
    daemon_client.generation_controls.save_generation_selection(
        paths,
        scope="conversation",
        conversation_id=conversation["id"],
        selection={"mode": "creative", "parameters": {"max_tokens": 777}},
    )
    control = daemon_client.generation_controls.resolve_generation_control(
        paths,
        provider="ollama",
        hermes_provider="custom",
        model="llama3.2",
        conversation_id=conversation["id"],
        turn_override={"mode": "fast", "parameters": {"reasoning_effort": "high"}},
    )

    assert control["mode"] == "fast"
    assert control["effective_parameters"]["temperature"] == 0.15
    assert control["parameters"]["temperature"]["source"] == "global_override"
    assert control["effective_parameters"]["max_tokens"] == 777
    assert control["parameters"]["max_tokens"]["source"] == "conversation_override"
    assert control["effective_parameters"]["reasoning_effort"] == "high"
    assert control["parameters"]["reasoning_effort"]["source"] == "turn_override"
    assert control["effective_parameters"]["max_iterations"] == 8


def test_desktop_and_weixin_use_same_generation_resolver(daemon_client, monkeypatch):
    _install_agent(daemon_client, monkeypatch)
    _save_local_provider(daemon_client)
    paths = daemon_client.config_paths.get_runtime_paths()
    desktop = daemon_client.conversations.create_conversation(title="桌面", paths=paths)
    weixin = daemon_client.conversations.create_conversation(title="微信", kind="weixin", paths=paths)
    for conversation in (desktop, weixin):
        daemon_client.generation_controls.save_generation_selection(
            paths,
            scope="conversation",
            conversation_id=conversation["id"],
            selection={"mode": "deep"},
        )

    asyncio.run(daemon_client.agent_runner.send_agent_message("桌面消息", desktop["id"], paths))
    asyncio.run(
        daemon_client.agent_runner.send_agent_message(
            "微信消息",
            weixin["id"],
            paths,
            route={"chat_id": "local-test", "user_id": "local-test", "chat_type": "private"},
        )
    )

    desktop_kwargs, weixin_kwargs = CapturingAgent.calls[-2:]
    for key in ("max_tokens", "max_iterations", "reasoning_config", "request_overrides"):
        assert desktop_kwargs[key] == weixin_kwargs[key]
    assert desktop_kwargs["enabled_toolsets"] == weixin_kwargs["enabled_toolsets"]


def test_unsupported_temperature_is_omitted_with_plain_chinese_reason(daemon_client, monkeypatch):
    paths = daemon_client.config_paths.get_runtime_paths()
    monkeypatch.setattr(
        daemon_client.generation_controls,
        "_model_metadata",
        lambda _provider, _hermes_provider, _model: (None, None),
    )
    control = daemon_client.generation_controls.resolve_generation_control(
        paths,
        provider="kimi",
        hermes_provider="kimi-coding",
        model="kimi-for-coding",
    )

    assert "temperature" not in control["runtime"]["request_overrides"]
    assert control["parameters"]["temperature"]["status"] == "locked"
    assert control["parameters"]["temperature"]["reason"] == "此模型由服务端控制随机性。"


def test_provider_parameter_rejection_downgrades_and_retries_once(daemon_client, monkeypatch):
    class RejectingAgent(CapturingAgent):
        def run_conversation(self, user_message, conversation_history=None, task_id=None):
            self.calls.append(self.kwargs)
            if len(self.calls) == 1:
                return {
                    "failed": True,
                    "error": "Unsupported parameter: top_p",
                    "messages": [],
                    "model": self.model,
                    "provider": self.provider,
                }
            return {
                "final_response": "安全重试成功",
                "messages": [],
                "api_calls": 1,
                "model": self.model,
                "provider": self.provider,
            }

    _install_agent(daemon_client, monkeypatch, RejectingAgent)
    _save_local_provider(daemon_client)
    paths = daemon_client.config_paths.get_runtime_paths()
    conversation = daemon_client.conversations.create_conversation(title="拒参重试", paths=paths)
    daemon_client.generation_controls.save_generation_selection(
        paths,
        scope="conversation",
        conversation_id=conversation["id"],
        selection={"mode": "creative"},
    )

    result = asyncio.run(daemon_client.agent_runner.send_agent_message("测试拒参", conversation["id"], paths))

    assert result["ok"] is True
    assert result["reply"] == "安全重试成功"
    assert len(RejectingAgent.calls) == 2
    assert RejectingAgent.calls[0]["request_overrides"]["top_p"] == 0.95
    assert "top_p" not in RejectingAgent.calls[1]["request_overrides"]
    assert result["generation_execution"]["automatic_downgrade"] is True
    assert result["generation_execution"]["retry_count"] == 1
    recorded = daemon_client.generation_controls._recorded_rejections(paths, "ollama", "llama3.2")
    assert "top_p" in recorded


def test_generation_modes_do_not_change_tools_or_safety_boundaries(daemon_client, monkeypatch):
    _install_agent(daemon_client, monkeypatch)
    _save_local_provider(daemon_client)
    paths = daemon_client.config_paths.get_runtime_paths()
    conversation = daemon_client.conversations.create_conversation(title="安全边界", paths=paths)
    calls = []
    for mode in ("fast", "deep"):
        daemon_client.generation_controls.save_generation_selection(
            paths,
            scope="conversation",
            conversation_id=conversation["id"],
            selection={"mode": mode},
        )
        asyncio.run(daemon_client.agent_runner.send_agent_message(mode, conversation["id"], paths))
        calls.append(CapturingAgent.calls[-1])

    assert calls[0]["enabled_toolsets"] == calls[1]["enabled_toolsets"]
    assert calls[0]["skip_memory"] == calls[1]["skip_memory"] is False
    assert calls[0]["skip_context_files"] == calls[1]["skip_context_files"] is True
    assert calls[0]["load_soul_identity"] == calls[1]["load_soul_identity"] is True
