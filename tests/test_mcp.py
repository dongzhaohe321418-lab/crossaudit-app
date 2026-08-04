from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from crossaudit import mcp
from crossaudit.errors import ConfigDenial

SERVER = r'''import json, sys
for line in sys.stdin:
    message=json.loads(line)
    if "id" not in message:
        continue
    method=message.get("method")
    if method=="initialize":
        result={"protocolVersion":"2025-11-25","capabilities":{"tools":{}},
                "serverInfo":{"name":"fixture","version":"1"}}
    elif method=="tools/list":
        result={"tools":[
            {"name":"lookup","description":"Look up one value",
             "inputSchema":{"type":"object","properties":{"query":{"type":"string"}}}},
            {"name":"mutate","description":"Change external state",
             "inputSchema":{"type":"object"}}]}
    elif method=="tools/call":
        args=message.get("params",{}).get("arguments",{})
        result={"content":[{"type":"text","text":"answer: "+args.get("query","")}],
                "structuredContent":{"value":42},"isError":False}
    else:
        print(json.dumps({"jsonrpc":"2.0","id":message["id"],
                          "error":{"code":-32601,"message":"missing"}}),flush=True)
        continue
    print(json.dumps({"jsonrpc":"2.0","id":message["id"],"result":result}),flush=True)
'''


def _stdio_payload(script, **extra):
    return {"name": "Fixture tools", "transport": "stdio",
            "command": sys.executable, "args": [str(script)],
            "approve_local_code": True, "enabled": True,
            "allowed_tools": ["lookup"], "max_calls_per_task": 3, **extra}


def test_stdio_child_environment_keeps_windows_runtime_bootstrap(monkeypatch):
    monkeypatch.setenv("SYSTEMROOT", r"C:\\Windows")
    monkeypatch.setenv("WINDIR", r"C:\\Windows")
    monkeypatch.setenv("TEMP", r"C:\\Temp")
    monkeypatch.setenv("CROSSAUDIT_AUDITOR_KEY", "must-not-cross-boundary")

    env = mcp._stdio_environment()

    assert env["SYSTEMROOT"] == r"C:\\Windows"
    assert env["WINDIR"] == r"C:\\Windows"
    assert env["TEMP"] == r"C:\\Temp"
    assert "CROSSAUDIT_AUDITOR_KEY" not in env


def test_stdio_server_is_initialized_listed_policy_gated_and_called(cfg, tmp_path):
    script = tmp_path / "fixture_mcp.py"
    script.write_text(SERVER)
    manager = mcp.Manager()

    server = manager.register(cfg, _stdio_payload(script))
    context = manager.agent_context(cfg)
    result = manager.call_agent(cfg, {
        "server_id": server["id"], "tool": "lookup",
        "arguments": {"query": "alpha"},
    }, chat_id="history", ordinal=1)

    assert server["protocol_version"] == "2025-11-25"
    assert [row["name"] for row in server["tools"]] == ["lookup", "mutate"]
    assert [row["name"] for row in context[0]["tools"]] == ["lookup"]
    assert result["status"] == "completed"
    assert result["content"][0]["text"] == "answer: alpha"
    assert result["structured_content"] == {"value": 42}
    call = manager.snapshot(cfg)["calls"][0]
    assert call["tool"] == "lookup" and call["chat_id"] == "history"
    assert "alpha" not in json.dumps(call)


def test_mcp_server_never_grants_unselected_or_new_tools(cfg, tmp_path):
    script = tmp_path / "fixture_mcp.py"
    script.write_text(SERVER)
    manager = mcp.Manager()
    server = manager.register(cfg, _stdio_payload(script))

    with pytest.raises(ConfigDenial, match="not approved"):
        manager.call_agent(cfg, {
            "server_id": server["id"], "tool": "mutate", "arguments": {}})
    with pytest.raises(ConfigDenial, match="calls-per-task limit"):
        manager.call_agent(cfg, {
            "server_id": server["id"], "tool": "lookup", "arguments": {}},
            ordinal=4)


def test_stdio_requires_exact_command_consent_and_never_uses_a_shell(cfg, tmp_path):
    script = tmp_path / "fixture_mcp.py"
    script.write_text(SERVER)
    manager = mcp.Manager()
    payload = _stdio_payload(script)
    payload["approve_local_code"] = False
    with pytest.raises(ConfigDenial, match="approve the exact"):
        manager.register(cfg, payload)
    payload["approve_local_code"] = True
    payload["command"] = f"{sys.executable} -c"
    with pytest.raises(ConfigDenial, match="not found or is not executable"):
        manager.register(cfg, payload)


def test_disabled_server_is_invisible_to_generator(cfg, tmp_path):
    script = tmp_path / "fixture_mcp.py"
    script.write_text(SERVER)
    manager = mcp.Manager()
    payload = _stdio_payload(script)
    payload["enabled"] = False
    server = manager.register(cfg, payload)
    assert manager.agent_context(cfg) == []
    with pytest.raises(ConfigDenial, match="not enabled"):
        manager.call_agent(cfg, {
            "server_id": server["id"], "tool": "lookup", "arguments": {}})


def test_new_server_cannot_blanket_enable_tools_before_user_reviews_list(cfg, tmp_path):
    script = tmp_path / "fixture_mcp.py"
    script.write_text(SERVER)
    payload = _stdio_payload(script, allow_all_tools=True)
    payload.pop("allowed_tools")
    with pytest.raises(ConfigDenial, match="review the advertised tool list"):
        mcp.Manager().register(cfg, payload)


def test_stdio_server_timeout_is_bounded_and_kills_the_child(cfg, tmp_path):
    script = tmp_path / "slow_mcp.py"
    script.write_text("import time; time.sleep(30)\n")
    payload = _stdio_payload(script)
    payload["timeout"] = 1
    started = time.monotonic()
    with pytest.raises(ConfigDenial, match="timed out"):
        mcp.Manager().register(cfg, payload)
    assert time.monotonic() - started < 5


def test_stdio_server_cannot_stream_an_unbounded_line(cfg, tmp_path):
    script = tmp_path / "oversized_mcp.py"
    script.write_text(
        "import sys\n"
        f"sys.stdout.buffer.write(b'x' * {mcp.MAX_MESSAGE_BYTES + 1} + b'\\n')\n"
        "sys.stdout.buffer.flush()\n")
    with pytest.raises(ConfigDenial, match="exceeded the safety limit"):
        mcp.Manager().register(cfg, _stdio_payload(script))


class HTTPFixture(BaseHTTPRequestHandler):
    def do_POST(self):
        message = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        method = message.get("method")
        if "id" not in message:
            self.send_response(202)
            self.end_headers()
            return
        if method == "initialize":
            result = {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}},
                      "serverInfo": {"name": "http-fixture", "version": "1"}}
        elif method == "tools/list":
            result = {"tools": [{"name": "search", "description": "Search",
                                  "inputSchema": {"type": "object"}}]}
        else:
            result = {"content": [{"type": "text", "text": "remote result"}]}
        body = json.dumps({"jsonrpc": "2.0", "id": message["id"],
                           "result": result}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        if method == "initialize":
            self.send_header("MCP-Session-Id", "fixture-session")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def test_loopback_streamable_http_initializes_and_preserves_session(cfg):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), HTTPFixture)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        manager = mcp.Manager()
        server = manager.register(cfg, {
            "name": "Local HTTP", "transport": "http",
            "url": f"http://127.0.0.1:{httpd.server_address[1]}/mcp",
            "enabled": True, "allowed_tools": ["search"],
            "max_calls_per_task": 2,
        })
        result = manager.call_agent(cfg, {
            "server_id": server["id"], "tool": "search", "arguments": {}})
        assert result["content"][0]["text"] == "remote result"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("url", [
    "http://example.com/mcp", "https://user:pass@example.com/mcp",
    "file:///tmp/server", "https://example.com/mcp?token=secret",
])
def test_remote_url_rejects_insecure_or_secret_bearing_forms(url):
    with pytest.raises(ConfigDenial):
        mcp._safe_url(url, allow_private=False)


def test_tools_and_skills_ui_exposes_project_policy_without_external_assets():
    from crossaudit.console.page import PAGE

    for text in (
        'data-view="tools"', 'id="mcp-modal"', 'id="mcp-form"',
        "Tools & Skills", "Add MCP server", "Local stdio", "Streamable HTTP",
        "I approve this exact local command", "Approved tool names",
        "Allow Generator to call the approved tools automatically",
        "Manage Skills", "/api/mcp", "data-mcp-configure",
    ):
        assert text in PAGE
    assert "eval(" not in PAGE
