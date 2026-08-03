"""Doctor must include its own deployment constraints in the final verdict."""
from __future__ import annotations

import argparse

from crossaudit.cli import main
from crossaudit.errors import EXIT_CONFIG


def test_non_admissible_install_makes_doctor_not_ready(cfg, monkeypatch, capsys):
    monkeypatch.chdir(cfg.root)
    monkeypatch.setattr(main._selfid, "identity", lambda: {
        "install_mode": "editable", "code_digest_sha256": "a" * 64,
        "project": "crossaudit", "version": "4.0.0", "lock_digest_sha256": None})
    code = main.cmd_doctor(argparse.Namespace(fix=False, online=False, json=False))
    out = capsys.readouterr().out
    assert code == EXIT_CONFIG
    assert "[FAIL] admission-capable" in out and "not ready" in out


def test_doctor_catches_impossible_shared_key_isolation(cfg, monkeypatch, capsys):
    import dataclasses

    strict = dataclasses.replace(cfg, isolation_minimum={
        "parametric": True, "contextual": True, "permissive": True})
    monkeypatch.chdir(cfg.root)
    monkeypatch.setattr(main, "load", lambda: strict)
    monkeypatch.setattr(main._selfid, "identity", lambda: {
        "install_mode": "wheel", "code_digest_sha256": "a" * 64,
        "project": "crossaudit", "version": "4.0.0", "lock_digest_sha256": None})
    monkeypatch.setenv(strict.auditor.key_env, "auditor-secret")
    monkeypatch.setenv(strict.generator_key_env or "CROSSAUDIT_GENERATOR_KEY",
                       "generator-secret")
    code = main.cmd_doctor(argparse.Namespace(fix=False, online=False, json=False))
    out = capsys.readouterr().out
    assert code == EXIT_CONFIG
    assert "[FAIL] isolation minimum" in out and "both roles' keys" in out


def test_doctor_reports_a_clone_without_git_identity(cfg, monkeypatch, capsys):
    monkeypatch.chdir(cfg.root)
    monkeypatch.setattr(main._selfid, "identity", lambda: {
        "install_mode": "wheel", "code_digest_sha256": "a" * 64,
        "project": "crossaudit", "version": "4.0.0", "lock_digest_sha256": None})
    real_git = main.git
    def no_identity(*args, **kwargs):
        if args[:2] in (("config", "user.name"), ("config", "user.email")):
            return ""
        return real_git(*args, **kwargs)
    monkeypatch.setattr(main, "git", no_identity)
    code = main.cmd_doctor(argparse.Namespace(fix=False, online=False, json=False))
    out = capsys.readouterr().out
    assert code == EXIT_CONFIG
    assert "[FAIL] git identity" in out and "git config user.name" in out
