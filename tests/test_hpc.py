from __future__ import annotations

from types import SimpleNamespace

import pytest

from crossaudit import hpc
from crossaudit.errors import ConfigDenial


class FakeSSH:
    def __init__(self, *, scheduler="slurm"):
        self.scheduler = scheduler
        self.calls = []
        self.fail_poll = False

    def available(self):
        return True

    def _alias(self, value):
        return hpc.OpenSSH._alias(value)

    def expanded(self, alias):
        self._alias(alias)
        return {"hostname": "login.cluster.example", "user": "researcher",
                "port": "22", "proxyjump": "gateway"}

    def run(self, alias, command, *, input_text=None, timeout=20,
            trust_first_key=False):
        self.calls.append((alias, command, input_text, timeout, trust_first_key))
        if "printf 'kernel" in command:
            sbatch = "yes" if self.scheduler == "slurm" else "no"
            return ("kernel\tLinux 6.8 x86_64\ncpus\t64\nmemory_kb\t1000000\n"
                    "gpus\tNVIDIA A100\n" + f"sbatch\t{sbatch}\n"
                    "squeue\tyes\nsacct\tyes\nscancel\tyes\n"
                    "module\tyes\nconda\tyes\napptainer\tyes\nsetsid\tyes\n"
                    "partitions\tcpu,gpu\n")
        if command.startswith("umask 077"):
            assert input_text and "set -o pipefail" in input_text
            return ""
        if "sbatch --parsable" in command:
            return "12345;cluster\n"
        if "nohup setsid sh -c" in command:
            return "8123\n"
        if "squeue -h" in command:
            if self.fail_poll:
                raise hpc.SSHFailure("VPN unavailable", code="host_unreachable")
            return "queue|RUNNING|00:02|gpu001\n"
        if "tail -c" in command:
            return "---stdout.log---\nprogress 50%\n---stderr.log---\nwarning\n"
        if "find . -type f" in command:
            return "results/final.csv\t4096\nstdout.log\t20\n../escape\t5\n"
        if "wc -c <" in command:
            return "4096\n"
        if command.startswith("scancel") or command.startswith("kill --"):
            return ""
        if "kill -0" in command:
            return "running|"
        return ""

    def stream(self, alias, command):
        raise AssertionError("streaming is covered by the server boundary")

    def send_file(self, alias, source, destination, *, timeout=3600):
        self.calls.append((alias, "send_file:" + destination, str(source), timeout, False))


def registered(manager, cfg, **extra):
    payload = {"alias": "hpc-login", "scratch": "/scratch/researcher",
               "concurrency": 3, "details": "Use the gpu partition", **extra}
    return manager.register(cfg, payload)


def test_register_uses_ssh_config_probe_and_stores_no_private_key(cfg):
    transport = FakeSSH()
    manager = hpc.Manager(transport)
    host = registered(manager, cfg, trust_first_key=True)

    assert host["alias"] == "hpc-login"
    assert host["hostname"] == "login.cluster.example"
    assert host["proxy_jump"] is True
    assert host["probe"]["scheduler"] == "slurm"
    assert host["probe"]["gpus"] == ["NVIDIA A100"]
    assert transport.calls[0][-1] is True
    serialized = str(manager.snapshot(cfg))
    assert "IdentityFile" not in serialized and "private" not in serialized


@pytest.mark.parametrize("scratch", ["relative/path", "/scratch/../etc", "/scratch\nrm"])
def test_register_rejects_unsafe_scratch_paths(cfg, scratch):
    with pytest.raises(ConfigDenial, match="absolute normalized"):
        registered(hpc.Manager(FakeSSH()), cfg, scratch=scratch)


def test_slurm_submission_is_detached_persistent_and_resource_validated(cfg):
    transport = FakeSSH()
    manager = hpc.Manager(transport)
    host = registered(manager, cfg)
    job = manager.submit(cfg, {
        "host_id": host["id"], "name": "protein-fold", "script": "echo started\nsleep 2",
        "nodes": 2, "cpus": 16, "gpus": 2, "memory": "64G",
        "walltime": "02:00:00", "partition": "gpu", "account": "lab-123",
    })

    assert job["scheduler"] == "slurm" and job["remote_id"] == "12345"
    assert job["status"] == "queued"
    upload = next(call for call in transport.calls if call[1].startswith("umask 077"))
    assert "#SBATCH --gpus=2" in upload[2]
    assert "#SBATCH --partition=gpu" in upload[2]
    assert (cfg.root / cfg.state_dir / "hpc" / "jobs" / job["id"] / "job.sh").is_file()

    restored = hpc.Manager(transport).snapshot(cfg)
    assert restored["jobs"][0]["remote_id"] == "12345"


def test_workstation_job_uses_remote_nohup_and_survives_local_manager(cfg):
    transport = FakeSSH(scheduler="workstation")
    manager = hpc.Manager(transport)
    host = registered(manager, cfg)
    job = manager.submit(cfg, {"host_id": host["id"], "script": "sleep 30"})

    assert job["scheduler"] == "workstation" and job["remote_id"] == "8123"
    assert any("nohup setsid sh -c" in call[1] and "</dev/null" in call[1]
               for call in transport.calls)
    assert hpc.Manager(transport).snapshot(cfg)["active"] == 1


def test_job_inputs_stream_to_remote_inputs_without_loading_into_prompt(cfg, tmp_path):
    transport = FakeSSH()
    manager = hpc.Manager(transport)
    host = registered(manager, cfg)
    source = tmp_path / "large-data.bin"
    source.write_bytes(b"binary\x00data")
    attachment = SimpleNamespace(name="large-data.bin", source=source,
                                 digest="abc123")

    job = manager.submit(cfg, {"host_id": host["id"], "script": "wc -c inputs/*"},
                         attachments=[attachment])

    assert job["inputs"] == [{"name": "large-data.bin", "bytes": 11,
                              "sha256": "abc123"}]
    assert any(call[1].endswith("/inputs/large-data.bin")
               for call in transport.calls if call[1].startswith("send_file:"))


def test_connection_loss_does_not_mark_remote_job_failed(cfg):
    transport = FakeSSH()
    manager = hpc.Manager(transport)
    host = registered(manager, cfg)
    job = manager.submit(cfg, {"host_id": host["id"], "script": "sleep 30"})
    transport.fail_poll = True

    manager.refresh(cfg)
    current = manager.snapshot(cfg)["jobs"][0]
    assert current["status"] == "queued"
    assert current["connection_error"] == "VPN unavailable"
    assert current["id"] == job["id"]


def test_live_status_logs_outputs_and_explicit_cancel(cfg):
    transport = FakeSSH()
    manager = hpc.Manager(transport)
    host = registered(manager, cfg)
    job = manager.submit(cfg, {"host_id": host["id"], "script": "echo hello"})

    assert manager.refresh(cfg)
    current = manager.snapshot(cfg)["jobs"][0]
    assert current["status"] == "running" and current["elapsed"] == "00:02"
    logs = manager.logs(cfg, job["id"])
    assert "progress 50%" in logs["stdout"] and "warning" in logs["stderr"]
    outputs = manager.outputs(cfg, job["id"])
    assert {row["path"] for row in outputs} == {"results/final.csv", "stdout.log"}
    cancelled = manager.cancel(cfg, job["id"])
    assert cancelled["status"] == "cancelled"
    assert any(call[1] == "scancel -- 12345" for call in transport.calls)
    assert any("find . -type f" in call[1] and "wc -c" in call[1]
               and "-maxdepth" not in call[1] and "stat -c" not in call[1]
               for call in transport.calls)


def test_job_payload_blocks_resource_and_identifier_injection(cfg):
    manager = hpc.Manager(FakeSSH())
    host = registered(manager, cfg)
    with pytest.raises(ConfigDenial, match="partition"):
        manager.submit(cfg, {"host_id": host["id"], "script": "true",
                             "partition": "gpu; rm -rf /"})
    with pytest.raises(ConfigDenial, match="wall time"):
        manager.submit(cfg, {"host_id": host["id"], "script": "true",
                             "walltime": "forever"})
    with pytest.raises(ConfigDenial, match="output path"):
        hpc._relative_output("../../etc/passwd")
    with pytest.raises(ConfigDenial, match="job name"):
        manager.submit(cfg, {"host_id": host["id"], "script": "true",
                             "name": "safe\n#SBATCH --account=other"})


def test_host_concurrency_limit_is_enforced_before_remote_upload(cfg):
    transport = FakeSSH()
    manager = hpc.Manager(transport)
    host = registered(manager, cfg, concurrency=1)
    manager.submit(cfg, {"host_id": host["id"], "script": "sleep 30"})
    before = len(transport.calls)

    with pytest.raises(ConfigDenial, match="concurrent job limit"):
        manager.submit(cfg, {"host_id": host["id"], "script": "sleep 30"})
    assert len(transport.calls) == before


def test_workstation_without_setsid_refuses_unmanageable_detach(cfg):
    transport = FakeSSH(scheduler="workstation")
    original = transport.run

    def no_setsid(alias, command, **kwargs):
        output = original(alias, command, **kwargs)
        return output.replace("setsid\tyes", "setsid\tno")

    transport.run = no_setsid
    manager = hpc.Manager(transport)
    host = registered(manager, cfg)
    with pytest.raises(ConfigDenial, match="setsid"):
        manager.submit(cfg, {"host_id": host["id"], "script": "sleep 30"})


def test_changed_host_key_is_never_auto_replaced():
    error = hpc._ssh_error("WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!")
    assert error.code == "host_key_changed"
    assert "will not replace" in error.reason


def test_ssh_alias_picker_follows_safe_includes(tmp_path):
    include = tmp_path / "conf.d"
    include.mkdir()
    (include / "lab.conf").write_text("Host gpu-login *.wild\n  HostName gpu\n")
    config = tmp_path / "config"
    config.write_text("Include conf.d/*.conf\nHost primary gateway?\n  HostName primary\n")

    assert hpc.ssh_aliases(config) == ["gpu-login", "primary"]


def test_compute_ui_exposes_guided_hosts_jobs_and_remote_outputs():
    from crossaudit.console.page import PAGE

    for text in (
        'data-view="compute"', 'id="compute-host-form"',
        'id="compute-job-form"', "Trust a new host key once",
        "I approve this remote execution", "Remote-owned execution",
        "Closing CrossAudit will not stop it", "data-hpc-logs",
        "data-hpc-outputs", "/api/hpc/file", "followComputeLogs",
    ):
        assert text in PAGE
    assert "StrictHostKeyChecking=no" not in PAGE


def test_project_menu_projects_remote_job_progress(cfg, monkeypatch):
    from crossaudit.console import projects

    monkeypatch.setattr(hpc.MANAGER, "snapshot", lambda *_args, **_kwargs: {
        "jobs": [{"name": "genome alignment", "host": "cluster-a",
                  "status": "running", "submitted": 1}],
    })
    row = projects._runtime(cfg, cfg)

    assert row["actor"] == "HPC · cluster-a"
    assert row["step"] == "genome alignment · running"
