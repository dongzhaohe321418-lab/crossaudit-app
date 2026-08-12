"""The build loop must not waive the custom-endpoint egress opt-in.

`crossaudit run` sends a key to a non-builtin origin only when the user passes
--allow-custom-endpoint or exports CROSSAUDIT_ALLOW_CUSTOM_ENDPOINT. The loop
calls the same cmd_run through a synthetic args object; if that object hardcodes
the opt-in, every build round silently becomes the quieter path around a rule
the verb enforces. These tests pin the args object to the environment gate.
"""
from __future__ import annotations

from crossaudit.cli.build import _Args
from crossaudit.cli.main import ALLOW_CUSTOM_ENV, _allow_custom


def test_loop_args_refuse_custom_endpoint_without_opt_in(monkeypatch):
    monkeypatch.delenv(ALLOW_CUSTOM_ENV, raising=False)
    args = _Args()
    assert args.allow_custom_endpoint is False
    # The gate cmd_run actually consults must agree: no flag, no env, no egress.
    assert _allow_custom(args) is False


def test_loop_args_honour_the_environment_opt_in(monkeypatch):
    monkeypatch.setenv(ALLOW_CUSTOM_ENV, "1")
    args = _Args()
    assert args.allow_custom_endpoint is True
    assert _allow_custom(args) is True
