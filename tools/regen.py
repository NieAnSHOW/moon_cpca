#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""regen.py -- the sole authoritative regeneration entry for moon_cpca.

Fixed pipeline (stop on first failure):

    1. python tools/gen_adcodes.py            (raw; generator self-check 6/6)
    2. moon fmt data/                         (package-level formatting)
    3. python tools/check_artifact.py --records --fields --levels --order --dup
    4. python tools/gen_golden.py             (raw)
    5. moon fmt testdata/
    6. python tools/check_golden.py
    7. git diff --exit-code
    8. git status --short                     (must be empty)

CLI:
    python tools/regen.py                    full regeneration
    python tools/regen.py --no-network-check wrapper-level zero-network audit
    python tools/regen.py --verbose          per-step command + duration on stdout

There is deliberately no --skip-fmt: skipping formatting would bypass the
delivery contract.

Exit codes:
    0  every step passed and the worktree is clean
    2  generation/check failure or timeout
    3  formatting failure (moon fmt returned non-zero)
    4  dirty worktree (git diff / git status non-empty)

Network guard: PEP 578 audit hooks are process-local and are NOT inherited by
subprocesses.  Under --no-network-check the wrapper therefore injects a
temporary ``sitecustomize.py`` into the child's ``PYTHONPATH``; it installs an
audit hook at interpreter startup, before any generator code runs.  The same
mechanism guards BOTH generator subprocesses (gen_adcodes.py, which also gets
its own --no-network-check flag, and gen_golden.py, which has no such flag).
Any socket/network audit event is recorded and aborts the child immediately.

Logs (repo-relative, git-ignored):
    _build/regen.log
    _build/regen_network.json   (generators list + total event count)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
LOG_REL = "_build/regen.log"
NETWORK_REL = "_build/regen_network.json"
STEP_TIMEOUT = 600.0
TOTAL_TIMEOUT = 1800.0

# Generator steps whose child processes must be covered by the network guard.
GENERATOR_STEPS = {"gen_adcodes": 1, "gen_golden": 4}
GENERATOR_ORDER = ("gen_adcodes", "gen_golden")

# The sitecustomize payload.  It is inert unless REGEN_NETWORK_EVENTS is set.
# The event file descriptor is opened BEFORE the audit hook is installed so
# that recording an event cannot recurse into the hook (open() is audited).
SITECUSTOMIZE = r'''# -*- coding: utf-8 -*-
"""Temporary regen wrapper network guard (injected via PYTHONPATH)."""
import json as _json
import os as _os
import sys as _sys

_events_path = _os.environ.get("REGEN_NETWORK_EVENTS")
if _events_path:
    try:
        _fd = _os.open(
            _events_path,
            _os.O_WRONLY | _os.O_APPEND | _os.O_CREAT,
            0o666,
        )
    except OSError:
        _fd = None

    if _fd is not None:
        # Local-only lookups that do not touch the network.  On Windows
        # ``platform.system()`` calls ``socket.gethostname()`` while
        # setuptools/pkg_resources is imported (a transitive dependency of
        # the vendored cpca oracle).  It resolves the local host name via
        # the kernel, opens no socket, and sends no packet, so it is
        # recorded but not treated as a network event.
        _LOCAL_ONLY = frozenset(("socket.gethostname",))
        _NETWORK_PREFIX = "socket."
        _NETWORK_EXTRA = frozenset(
            ("urllib.Request", "http.client.connect", "http.client.send")
        )

        def _emit(payload):
            try:
                _os.write(
                    _fd,
                    (_json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"),
                )
                _os.fsync(_fd)
            except Exception:
                pass

        def _record(event, args):
            _emit(
                {
                    "event": event,
                    "args": repr(args)[:400],
                    "ignored_local": False,
                }
            )
            try:
                _sys.stderr.write(
                    "[regen-network-guard] blocked audit event: %s\n" % event
                )
                _sys.stderr.flush()
            except Exception:
                pass
            # Hard exit: no traceback, parent sees a non-zero child status.
            _os._exit(97)

        def _ignore(event, args):
            _emit(
                {
                    "event": event,
                    "args": repr(args)[:400],
                    "ignored_local": True,
                }
            )

        def _hook(event, args):
            if event in _LOCAL_ONLY:
                _ignore(event, args)
            elif event.startswith(_NETWORK_PREFIX) or event in _NETWORK_EXTRA:
                _record(event, args)

        _sys.addaudithook(_hook)
'''


def _display_argv(argv: Sequence[str]) -> str:
    """Command rendering with a machine-independent interpreter name."""
    parts = list(argv)
    if parts and os.path.normcase(parts[0]) == os.path.normcase(sys.executable):
        parts[0] = "python"
    return " ".join(parts)


def _first_error_line(stdout: str, stderr: str) -> str:
    for text in (stderr, stdout):
        for line in text.splitlines():
            line = line.strip()
            if line:
                return line[:500]
    return "(no output)"


class Regen:
    def __init__(self, network_check: bool, verbose: bool) -> None:
        self.network_check = network_check
        self.verbose = verbose
        self.started = time.monotonic()
        self.deadline = self.started + TOTAL_TIMEOUT
        self.build = ROOT / "_build"
        self.build.mkdir(parents=True, exist_ok=True)
        self.log = (ROOT / LOG_REL).open("w", encoding="utf-8", newline="\n")
        self.guard_dir: Optional[Path] = None
        self.network: Dict[str, Any] = {
            "mode": "no-network-check" if network_check else "default",
            "generators": [],
            "events": 0,
            "details": {},
        }

    # -- logging ---------------------------------------------------------
    def log_write(self, text: str) -> None:
        self.log.write(text)
        self.log.flush()

    def log_section(self, title: str) -> None:
        self.log_write("\n=== %s ===\n" % title)

    # -- network guard ---------------------------------------------------
    def setup_guard(self) -> None:
        self.guard_dir = Path(tempfile.mkdtemp(prefix="regen_net_guard_"))
        (self.guard_dir / "sitecustomize.py").write_text(
            SITECUSTOMIZE, encoding="utf-8", newline="\n"
        )
        self.log_write(
            "network-guard: injected sitecustomize.py for child generators\n"
        )

    def guard_env(self, step_name: str, base: Dict[str, str]) -> Tuple[Dict[str, str], Path]:
        if self.guard_dir is None:
            self.setup_guard()
        events_path = self.guard_dir / ("%s.events.jsonl" % step_name)
        events_path.write_text("", encoding="utf-8")
        env = dict(base)
        old = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            str(self.guard_dir) + (os.pathsep + old if old else "")
        )
        env["REGEN_NETWORK_EVENTS"] = str(events_path)
        return env, events_path

    def collect_events(self, step_name: str, events_path: Path) -> List[Dict[str, Any]]:
        blocked: List[Dict[str, Any]] = []
        ignored: List[Dict[str, Any]] = []
        try:
            text = events_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                record = {"event": "unparsable", "args": line[:400], "ignored_local": False}
            if record.get("ignored_local"):
                ignored.append(record)
            else:
                blocked.append(record)
        self.network["generators"].append(step_name)
        self.network["details"][step_name] = {
            "events": len(blocked),
            "event_list": blocked,
            "ignored_local_events": len(ignored),
            "ignored_local_list": ignored,
        }
        self.network["events"] += len(blocked)
        if blocked:
            for ev in blocked:
                self.log_write(
                    "network-guard: %s blocked %s %s\n"
                    % (step_name, ev.get("event"), ev.get("args", ""))
                )
        if ignored:
            for ev in ignored:
                self.log_write(
                    "network-guard: %s allowed local-only %s\n"
                    % (step_name, ev.get("event"))
                )
        return blocked

    def cleanup_guard(self) -> None:
        if self.guard_dir is not None:
            shutil.rmtree(self.guard_dir, ignore_errors=True)
            self.guard_dir = None

    def write_network_report(self) -> None:
        if not self.network["generators"]:
            self.network["generators"] = []
        payload = dict(self.network)
        path = ROOT / NETWORK_REL
        try:
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        except OSError as exc:
            self.log_write("network-report: write failed: %s\n" % exc)

    # -- steps -----------------------------------------------------------
    def run_step(
        self,
        number: int,
        name: str,
        argv: Sequence[str],
        step_class: str,
    ) -> Dict[str, Any]:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            result = self.finish_step(
                number,
                name,
                argv,
                2,
                "",
                "total wrapper timeout exceeded before step start (budget %ds)\n"
                % int(TOTAL_TIMEOUT),
                True,
            )
            result["duration"] = 0.0
            result["timeout_limit"] = 0.0
            result["total_timeout"] = True
            return result
        timeout = min(STEP_TIMEOUT, remaining)

        base_env = dict(os.environ)
        base_env["PYTHONIOENCODING"] = "utf-8"
        events_path: Optional[Path] = None
        if self.network_check and name in GENERATOR_STEPS:
            base_env, events_path = self.guard_env(name, base_env)

        cmdline = _display_argv(argv)
        self.log_section("STEP %d %s" % (number, name))
        self.log_write("$ %s\n" % cmdline)
        if self.verbose:
            print("CMD  %s" % cmdline, flush=True)
            print("TIME step %d start" % number, flush=True)

        started = time.monotonic()
        try:
            proc = subprocess.run(
                list(argv),
                cwd=str(ROOT),
                env=base_env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )
            stdout = proc.stdout.decode("utf-8", "replace")
            stderr = proc.stderr.decode("utf-8", "replace")
            code = proc.returncode
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or b"").decode("utf-8", "replace")
            stderr = (exc.stderr or b"").decode("utf-8", "replace")
            code = 2
            timed_out = True
            stderr = (
                "timeout: step killed after the %.1fs limit\n" % timeout
            ) + stderr
        except OSError as exc:
            stdout = ""
            stderr = "cannot execute: %s" % exc
            code = -2
            timed_out = False

        duration = time.monotonic() - started

        if name == "git_status" and code == 0 and stdout.strip():
            # `git status --short` succeeded but the worktree is dirty: this
            # is the wrapper's dirty-tree signal, not a git failure.
            code = 1
            stderr = ("git status --short is not empty\n" + stderr).strip() + "\n"

        if events_path is not None:
            events = self.collect_events(name, events_path)
            if events:
                # Network violation is a generation failure regardless of the
                # child's own exit status.  Report the wrapper-level exit code
                # (2) rather than the child's internal sentinel (97).
                code = 2
                event_names = ", ".join(
                    sorted({str(ev.get("event", "?")) for ev in events})
                )
                stderr = (
                    "[regen-network-guard] %d socket/network audit event(s) "
                    "from %s: %s\n" % (len(events), name, event_names)
                ) + stderr

        result = self.finish_step(number, name, argv, code, stdout, stderr, timed_out)
        result["duration"] = duration
        result["timeout_limit"] = timeout
        result["total_timeout"] = bool(timed_out and timeout < STEP_TIMEOUT)
        if self.verbose:
            print("TIME step %d %.3fs" % (number, duration), flush=True)
        return result

    def finish_step(
        self,
        number: int,
        name: str,
        argv: Sequence[str],
        code: int,
        stdout: str,
        stderr: str,
        timed_out: bool,
    ) -> Dict[str, Any]:
        print("STEP %d %s %d" % (number, name, code), flush=True)
        self.log_write("[exit %d]\n" % code)
        if stdout:
            self.log_write("--- stdout ---\n%s\n" % stdout.rstrip("\n"))
        if stderr:
            self.log_write("--- stderr ---\n%s\n" % stderr.rstrip("\n"))
        if self.verbose and stdout:
            sys.stdout.write(stdout if stdout.endswith("\n") else stdout + "\n")
            sys.stdout.flush()
        if self.verbose and stderr:
            sys.stderr.write(stderr if stderr.endswith("\n") else stderr + "\n")
            sys.stderr.flush()
        return {
            "n": number,
            "name": name,
            "argv": _display_argv(argv),
            "exit": code,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": timed_out,
        }

    # -- pipeline --------------------------------------------------------
    def pipeline(self) -> List[Tuple[int, str, List[str], str]]:
        py = sys.executable
        gen_adcodes = [py, "tools/gen_adcodes.py"]
        if self.network_check:
            gen_adcodes.append("--no-network-check")
        return [
            (1, "gen_adcodes", gen_adcodes, "generate"),
            (2, "fmt_data", ["moon", "fmt", "data/"], "format"),
            (
                3,
                "check_artifact",
                [
                    py,
                    "tools/check_artifact.py",
                    "--records",
                    "--fields",
                    "--levels",
                    "--order",
                    "--dup",
                ],
                "check",
            ),
            (4, "gen_golden", [py, "tools/gen_golden.py"], "generate"),
            (5, "fmt_testdata", ["moon", "fmt", "testdata/"], "format"),
            (6, "check_golden", [py, "tools/check_golden.py"], "check"),
            (7, "git_diff", ["git", "diff", "--exit-code"], "git"),
            (8, "git_status", ["git", "status", "--short"], "git"),
        ]

    @staticmethod
    def failure_exit(step_class: str) -> int:
        if step_class == "format":
            return 3
        if step_class == "git":
            return 4
        return 2

    def report_failure(self, result: Dict[str, Any], step_class: str) -> int:
        if result["timed_out"]:
            # Spec §3.3: every timeout exits 2, regardless of step class.
            limit = float(result.get("timeout_limit") or 0.0)
            if result.get("total_timeout"):
                if limit > 0:
                    detail = (
                        "step timed out after %.1fs (actual limit %.1fs; "
                        "total wrapper budget exhausted)"
                        % (result.get("duration", 0.0), limit)
                    )
                else:
                    detail = "total wrapper timeout exceeded before step start"
            else:
                detail = "step timed out after %.1fs (actual limit %.1fs)" % (
                    result.get("duration", 0.0),
                    limit,
                )
            exit_code = 2
        else:
            exit_code = self.failure_exit(step_class)
            if result["exit"] == -2:
                detail = "command could not be executed"
            else:
                detail = _first_error_line(result["stdout"], result["stderr"])
            if result["name"] == "git_status" and result["stdout"].strip():
                detail = result["stdout"].strip().splitlines()[0][:500]
                exit_code = 4

        sys.stderr.write("regen: step %d %s failed\n" % (result["n"], result["name"]))
        sys.stderr.write("regen: command: %s\n" % result["argv"])
        sys.stderr.write("regen: exit: %d\n" % result["exit"])
        sys.stderr.write("regen: error: %s\n" % detail)
        sys.stderr.write("regen: exit-code: %d\n" % exit_code)
        sys.stderr.write("regen: log: %s\n" % LOG_REL)
        sys.stderr.flush()
        self.log_write(
            "RESULT FAIL step=%d name=%s class=%s exit-code=%d error=%s\n"
            % (result["n"], result["name"], step_class, exit_code, detail)
        )
        return exit_code

    def run(self) -> int:
        self.log_write(
            "regen: %s\nroot=%s\nargs: --no-network-check=%s --verbose=%s\n"
            % (
                time.strftime("%Y-%m-%dT%H:%M:%S"),
                ".",
                self.network_check,
                self.verbose,
            )
        )
        if self.network_check:
            self.network["generators"] = []
            self.network["details"] = {}
            self.network["events"] = 0
            self.log_write(
                "network-guard: enabled for child generators %s\n"
                % ", ".join(GENERATOR_ORDER)
            )

        try:
            if self.network_check:
                self.setup_guard()
            for number, name, argv, step_class in self.pipeline():
                result = self.run_step(number, name, argv, step_class)
                failed = result["exit"] != 0
                if name == "git_status" and result["stdout"].strip():
                    failed = True
                if result["timed_out"]:
                    failed = True
                if failed:
                    print("REGEN FAIL", flush=True)
                    return self.report_failure(result, step_class)
            print("REGEN OK", flush=True)
            self.log_write("RESULT OK\n")
            return 0
        finally:
            self.write_network_report()
            self.cleanup_guard()
            self.log.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="regen.py",
        description=(
            "Authoritative regeneration entry: generate, format, check, "
            "and verify a clean worktree."
        ),
    )
    parser.add_argument(
        "--no-network-check",
        action="store_true",
        help=(
            "wrapper-level zero-network audit for BOTH generator "
            "subprocesses; writes _build/regen_network.json"
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print every step command and duration to stdout",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    runner = Regen(network_check=args.no_network_check, verbose=args.verbose)
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
