"""Git reads, with the tree as the only source of truth.

Every path here is materialised from a git object, never from the working
directory: a working tree can differ from the commit under audit, and an audit
that reads uncommitted bytes is auditing something no third party can replay.
Symlinks are refused rather than followed, so an increment cannot point the
auditor at /etc or at a file outside the tree.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .errors import ConfigDenial, IntegrityDenial

MAX_BLOB_BYTES = 512 * 1024

#: A generous-but-finite ceiling for the document types ``blob_limit`` leaves
#: uncapped (.pdf/.docx). Their container is hashed whole, so no product quota
#: is imposed on real documents — but a pathological blob (a gigabyte committed
#: under a .pdf name) must never be buffered in full. Anything at or below this
#: bound is returned byte-for-byte exactly as before, so every normal document
#: hashes identically; only a blob past it is refused. Overridable via
#: ``CROSSAUDIT_MAX_DOC_BYTES`` for a deployment that genuinely audits larger
#: documents. It MUST match between the audit host and the verify host, exactly
#: as ``blob_limit``'s caps must: a boundary that differed across the two would
#: let one side read a document the other recorded as too-large. 64 MiB sits far
#: above real-world .docx/.pdf sizes.
MAX_DOC_BYTES = 64 * 1024 * 1024

#: The deterministic stand-in ``read_blob`` returns for a document blob past the
#: guard, instead of allocating the whole thing. Both the audit path and
#: ``receipt/verify.py`` go through the SAME ``read_blob`` and so hash THIS exact
#: constant for an oversize document — audit and verify agree byte-for-byte that
#: the document was too large rather than one of them OOMing. It leads with a
#: non-UTF-8 byte (``\xff`` can never start a UTF-8 sequence) so the prompt
#: renderer routes it through document extraction (which reports "document too
#: large to audit") exactly as it does for a real binary, and it is far too
#: specific to collide with any genuine sub-guard document.
OVERSIZE_DOCUMENT_MARKER = (
    b"\xff\xfeCROSSAUDIT:DOCUMENT-TOO-LARGE-TO-AUDIT:"
    b"audit-and-verify-share-this-exact-marker\xfe\xff")

#: Read granularity for :func:`_stream_blob`; the peak memory a bounded read
#: holds beyond its cap is one of these chunks, not the blob's full size.
_BLOB_READ_CHUNK = 1 << 20

#: Every build round drives commit + rev-parse through ``git()``, so an
#: unbounded git is a hang that pins the run in an ACTIVE state forever and the
#: single-run guard then locks out the whole project. A stale ``.git/index.lock``,
#: a blocking hook, a credential/GPG prompt, or an NFS/fsevents stall are the
#: usual culprits. The bound is deliberately generous — a legitimate large-tree
#: commit must never be cut short — and overridable via ``CROSSAUDIT_GIT_TIMEOUT``
#: (seconds) for unusually large repositories. Mirrors how mcp.py, hpc.py and
#: codex_subscription.py already bound their subprocesses.
GIT_TIMEOUT_S = 240.0


def _git_timeout() -> float:
    raw = os.environ.get("CROSSAUDIT_GIT_TIMEOUT", "").strip()
    if raw:
        try:
            value = float(raw)
        except ValueError:
            value = 0.0
        if value > 0:
            return value
    return GIT_TIMEOUT_S


def git(*args: str, cwd: Path, check: bool = True) -> str:
    timeout = _git_timeout()
    try:
        proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        # A timed-out git reaches a terminal outcome instead of wedging: the
        # loop treats ConfigDenial from the commit as ``commit_refused`` and
        # stops cleanly, freeing the run slot.
        raise ConfigDenial(
            f"git {' '.join(args)} did not finish within {timeout:.0f}s and was "
            f"abandoned (a stale index.lock, a blocking hook, or a credential/GPG "
            f"prompt can hang git); raise CROSSAUDIT_GIT_TIMEOUT if this is a "
            f"legitimately large operation", cwd=str(cwd)) from exc
    if check and proc.returncode != 0:
        raise ConfigDenial(f"git {' '.join(args)} failed: {proc.stderr.strip()[:200]}",
                           cwd=str(cwd))
    return proc.stdout.strip()


def is_repo(path: Path) -> bool:
    return subprocess.run(["git", "-C", str(path), "rev-parse", "--git-dir"],
                          capture_output=True).returncode == 0


def resolve(repo: Path, rev: str) -> tuple[str, str]:
    """(commit sha, tree sha) for a revision, both full length."""
    sha = git("rev-parse", f"{rev}^{{commit}}", cwd=repo)
    tree = git("rev-parse", f"{rev}^{{tree}}", cwd=repo)
    if len(sha) != 40:
        raise ConfigDenial(f"could not resolve {rev!r} to a full commit sha", repo=str(repo))
    return sha, tree


def parent(repo: Path, sha: str) -> str | None:
    out = git("rev-list", "--parents", "-n", "1", sha, cwd=repo).split()
    return out[1] if len(out) > 1 else None


def changed_paths(repo: Path, sha: str) -> list[str]:
    """The paths this commit touched: the increment, as git already knows it.

    Scope derived from the commit itself rather than asked of the user. A first
    commit has no parent, so everything in the tree counts as introduced.
    """
    if parent(repo, sha):
        raw = git("diff-tree", "--no-commit-id", "--name-only", "-r", sha, cwd=repo,
                  check=False)
    else:
        raw = git("ls-tree", "-r", "--name-only", sha, cwd=repo, check=False)
    return [line for line in raw.splitlines() if line.strip()]


def entries(repo: Path, sha: str, prefix: str = "") -> list[tuple[str, str, str]]:
    """(mode, path, blob-sha) for every file in the commit's tree under prefix."""
    args = ["ls-tree", "-r", "-z", sha]
    if prefix:
        args += ["--", prefix]
    raw = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)
    if raw.returncode != 0:
        raise ConfigDenial(f"git ls-tree failed: {raw.stderr.strip()[:200]}", repo=str(repo))
    out = []
    for rec in raw.stdout.split("\0"):
        if not rec.strip():
            continue
        meta, path = rec.split("\t", 1)
        mode, otype, blob = meta.split()
        if otype != "blob":
            continue
        out.append((mode, path, blob))
    return out


def blob_limit(path: str) -> int | None:
    """Read bound for one path — the single policy for audit AND verification.

    PDF/DOCX content is audited through bounded semantic extraction, but the
    container itself must remain complete for validation and receipt hashing:
    truncating the ZIP/PDF first would make every larger document look corrupt.
    No product quota is imposed on documents; physical memory/disk remain the
    real machine limits.

    The receipt manifest hashes whatever this policy reads, and verification
    re-reads under it. Both sides must call this one function: if the two read
    policies ever drift, every document past the generic bound verifies as
    "manifest mismatch" forever, denying receipts that are in fact intact.
    """
    return None if Path(path).suffix.lower() in {".pdf", ".docx"} else MAX_BLOB_BYTES


def _max_doc_bytes() -> int:
    raw = os.environ.get("CROSSAUDIT_MAX_DOC_BYTES", "").strip()
    if raw:
        try:
            value = int(raw)
        except ValueError:
            value = 0
        if value > 0:
            return value
    return MAX_DOC_BYTES


def _stream_blob(repo: Path, blob: str, cap: int) -> tuple[bytes, bool]:
    """Read at most ``cap + 1`` bytes of a git blob without buffering the rest.

    Returns ``(data, had_more)`` where ``len(data) <= cap + 1`` and ``had_more``
    is True iff the blob is strictly larger than ``cap``. ``git cat-file`` is
    stopped the instant the bound is reached, so a multi-gigabyte blob costs at
    most ``cap + 1`` bytes of memory and never streams in full. A blob that does
    not exist raises ``IntegrityDenial`` exactly as the buffered read did.
    """
    proc = subprocess.Popen(["git", "cat-file", "blob", blob], cwd=str(repo),
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    want = cap + 1
    chunks: list[bytes] = []
    got = 0
    try:
        stream = proc.stdout
        assert stream is not None
        while got < want:
            chunk = stream.read(min(want - got, _BLOB_READ_CHUNK))
            if not chunk:
                break
            chunks.append(chunk)
            got += len(chunk)
    finally:
        forced = got >= want
        if forced:
            # We already have enough bytes; terminate git rather than let it
            # stream the rest of a huge blob (kill if it ignores the signal).
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        else:
            proc.wait()
        if proc.stdout is not None:
            proc.stdout.close()
    data = b"".join(chunks)
    # Only a git that finished on its own can report a real failure; a git we
    # terminated after the bound exits on a signal we must not misread as an
    # unreadable blob.
    if not forced and proc.returncode not in (0, None):
        raise IntegrityDenial(f"cannot read blob {blob[:12]}", repo=str(repo))
    return data, got >= want


def read_cap(path: str) -> int:
    """The concrete byte ceiling a read of `path` is bounded to.

    ``blob_limit`` returns ``None`` for the document types whose container is
    hashed whole; this resolves that to the finite document guard so a caller
    that needs an actual number (the working-tree check) shares one policy with
    the blob reader instead of inventing its own.
    """
    cap = blob_limit(path)
    return _max_doc_bytes() if cap is None else cap


def read_blob(repo: Path, blob: str, *,
              limit: int | None = MAX_BLOB_BYTES) -> tuple[bytes, bool]:
    """Blob bytes and whether they were truncated at `limit`.

    The bytes are streamed and the child ``git`` is stopped as soon as the read
    bound is reached, so peak memory is the bound rather than the blob's full
    size. For every normal input this is byte-identical to the old
    buffer-then-truncate — the receipt manifest hashes exactly what it hashed
    before, so I8 holds. Only two things change: memory is now capped, and a
    document blob past :data:`MAX_DOC_BYTES` is refused with a deterministic
    marker instead of being allocated whole.
    """
    if limit is not None:
        data, had_more = _stream_blob(repo, blob, limit)
        return (data[:limit], True) if had_more else (data, False)
    # Uncapped document types (.pdf/.docx): the container is hashed whole, but a
    # blob past the document guard is never buffered. Both the audit path and
    # receipt/verify.py call THIS function, so each hashes the same
    # OVERSIZE_DOCUMENT_MARKER for an oversize document — the two sides record
    # (and re-verify) "too large" identically instead of one of them OOMing.
    data, had_more = _stream_blob(repo, blob, _max_doc_bytes())
    if had_more:
        return OVERSIZE_DOCUMENT_MARKER, False
    return data, False


def materialise(repo: Path, sha: str, prefix: str = "",
                only: list[str] | None = None) -> tuple[dict[str, bytes], list[str]]:
    """Read an increment straight out of the tree.

    Returns (path -> bytes, notes). Symlinks and submodules are refused; a
    truncated blob is reported, and truncation must never end in PASS (I8).
    """
    files: dict[str, bytes] = {}
    notes: list[str] = []
    wanted = set(only) if only is not None else None
    for mode, path, blob in entries(repo, sha, prefix):
        if wanted is not None and path not in wanted:
            continue

        if mode == "120000":
            raise IntegrityDenial(f"increment contains a symlink: {path}", sha=sha)
        if mode == "160000":
            raise IntegrityDenial(f"increment contains a submodule: {path}", sha=sha)
        data, truncated = read_blob(repo, blob, limit=blob_limit(path))
        if truncated:
            notes.append(f"truncated: {path}")
        files[path] = data
    return files, notes


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor",
                           ancestor, descendant], capture_output=True).returncode == 0


def commit_exists(repo: Path, sha: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"],
                          capture_output=True).returncode == 0
