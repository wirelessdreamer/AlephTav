"""Managed ``codex app-server`` subprocess and JSON-RPC client (FR-1, FR-2, FR-7).

The FastAPI backend owns the local Codex subprocess; the browser never speaks to
Codex and never sees account credentials. Transport is stdio by default and no
listener socket is opened.

Messages are pumped synchronously: :meth:`CodexAppServerClient.request` writes a
request and then reads until the matching response arrives, dispatching
notifications and server-initiated requests along the way. That keeps the client
free of threads and makes it testable against a fake transport, which is what the
tests use so no live ChatGPT account is needed.

API requests reach the one client from concurrent threads, so each exchange -- a
request, or a turn from start to completion -- holds a lock. Two readers on the same
stdout would swallow each other's responses and turn notifications, leaving both
waiting forever.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.errors import GenerationError

CLIENT_NAME = "alephtav-workbench"
CLIENT_VERSION = "0.1.0"
PROVIDER_NAME = "codex-app-server"

STATUS_NOT_INSTALLED = "not_installed"
STATUS_AVAILABLE = "available"
STATUS_CONNECTING = "connecting"
STATUS_READY = "ready"
STATUS_NOT_SIGNED_IN = "not_signed_in"
STATUS_BUSY = "busy"
STATUS_ERROR = "error"

#: Server-initiated requests that would let Codex touch the machine. Translation
#: mode denies every one of them (FR-7).
APPROVAL_METHODS = frozenset(
    {
        "item/commandExecution/requestApproval",
        "item/fileChange/requestApproval",
        "item/tool/call",
        "applyPatchApproval",
        "execCommandApproval",
    }
)

#: The refusal each approval method expects. v2 requests take "decline", the
#: legacy ones take "denied", and a dynamic tool call reports an unsuccessful run.
DENIAL_RESPONSES: dict[str, dict[str, Any]] = {
    "item/commandExecution/requestApproval": {"decision": "decline"},
    "item/fileChange/requestApproval": {"decision": "decline"},
    "item/tool/call": {"contentItems": [], "success": False},
    "applyPatchApproval": {"decision": "denied"},
    "execCommandApproval": {"decision": "denied"},
}

#: Server-initiated requests that ask a human something. Translation turns run
#: unattended, so these are declined rather than denied.
INPUT_METHODS = frozenset({"item/tool/requestUserInput"})

DENIED_MESSAGE = "Translation mode does not permit system changes."

#: How long a turn may go without a single message from Codex before it is stopped.
#: A healthy turn streams events throughout; silence this long means the upstream
#: model stream has stalled, and waiting on it would hold the client indefinitely.
STALL_TIMEOUT_SECONDS = 600.0

#: A turn that keeps streaming can still be stuck: the model can run away, emitting
#: blank space or repetition that never closes the answer. Healthy turns finish in a
#: few minutes and a few thousand characters; these bound the bad ones.
TURN_TIMEOUT_SECONDS = 1200.0
MAX_ANSWER_CHARS = 200_000
#: This much unbroken whitespace at the end of the answer means it has run away.
BLANK_RUN_CHARS = 2_000


class Transport(Protocol):
    """Line-delimited JSON transport to the app server."""

    def send(self, message: dict[str, Any]) -> None: ...

    def readline(self) -> str: ...

    def close(self) -> None: ...


class StdioTransport:
    """Real transport: a ``codex app-server`` child process over stdio."""

    def __init__(self, executable: str = "codex") -> None:
        # Resolve through PATH/PATHEXT before spawning. On Windows the real
        # entry point is codex.CMD; handing Popen the bare name raises
        # WinError 2, "The system cannot find the file specified".
        resolved = shutil.which(executable) or executable
        # Run Codex in an empty directory rather than the repository. From the repo it
        # reads AGENTS.md and explores the codebase before every answer, which slows each
        # turn and adds commentary; the prompt already carries all the evidence.
        self._workdir = tempfile.mkdtemp(prefix="alephtav-codex-")
        self._process = subprocess.Popen(  # noqa: S603
            [resolved, "app-server", "--listen", "stdio://"],
            cwd=self._workdir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )

    def send(self, message: dict[str, Any]) -> None:
        if self._process.stdin is None:  # pragma: no cover - defensive
            raise GenerationError("Codex app server stdin is closed")
        self._process.stdin.write(json.dumps(message) + "\n")
        self._process.stdin.flush()

    def readline(self) -> str:
        if self._process.stdout is None:  # pragma: no cover - defensive
            return ""
        return self._process.stdout.readline()

    def close(self) -> None:
        if self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:  # pragma: no cover - best effort shutdown
                self._process.kill()
        shutil.rmtree(self._workdir, ignore_errors=True)


def codex_executable() -> str | None:
    """Path to the local ``codex`` binary, or None when it is not installed."""
    return shutil.which("codex")


@dataclass
class CodexAppServerClient:
    """JSON-RPC client for a managed app-server process."""

    transport: Transport | None = None
    executable: str = "codex"
    _next_id: int = 1
    initialized: bool = False
    denied_events: list[dict[str, Any]] = field(default_factory=list)
    notifications: list[dict[str, Any]] = field(default_factory=list)
    on_notification: Callable[[dict[str, Any]], None] | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    #: Guards writes and request ids. An interrupt writes while a turn holds ``_lock``.
    _send_lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    #: Threads open in this app-server process. A thread belongs to the process that
    #: started or resumed it, so one saved before a restart must be resumed first.
    _threads: set[str] = field(default_factory=set, repr=False, compare=False)
    #: (thread_id, turn_id) of the turn being pumped, so another request can stop it.
    active_turn: tuple[str, str] | None = field(default=None, repr=False, compare=False)
    stall_timeout: float = STALL_TIMEOUT_SECONDS
    turn_timeout: float = TURN_TIMEOUT_SECONDS
    max_answer_chars: int = MAX_ANSWER_CHARS
    blank_run_chars: int = BLANK_RUN_CHARS
    _last_message_at: float = field(default=0.0, repr=False, compare=False)
    _turn_started_at: float = field(default=0.0, repr=False, compare=False)
    _streamed_chars: int = field(default=0, repr=False, compare=False)
    _stream_tail: str = field(default="", repr=False, compare=False)
    #: Why the watchdog stopped the turn, reported in place of a bare "stopped".
    _stop_reason: str | None = field(default=None, repr=False, compare=False)
    #: The account's default model, read once from ``model/list``. Without it a turn
    #: runs whatever ``~/.codex/config.toml`` names, which the account may not be
    #: entitled to use.
    _default_model: str | None = field(default=None, repr=False, compare=False)

    def _ensure_transport(self) -> Transport:
        if self.transport is None:
            if shutil.which(self.executable) is None:
                raise GenerationError(f"Codex executable not found on PATH: {self.executable}")
            self.transport = StdioTransport(self.executable)
        return self.transport

    # -- JSON-RPC plumbing -------------------------------------------------

    def _respond(self, request_id: Any, result: dict[str, Any]) -> None:
        with self._send_lock:
            self._ensure_transport().send({"jsonrpc": "2.0", "id": request_id, "result": result})

    def _send_request(self, method: str, params: Any) -> int:
        with self._send_lock:
            request_id = self._next_id
            self._next_id += 1
            self._ensure_transport().send(
                {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            )
        return request_id

    def _handle_server_request(self, message: dict[str, Any]) -> None:
        """Deny anything that would let Codex change the system (FR-7)."""
        method = message.get("method", "")
        if method in APPROVAL_METHODS:
            self.denied_events.append({"method": method, "params": message.get("params")})
            self._respond(message.get("id"), DENIAL_RESPONSES[method])
        elif method in INPUT_METHODS:
            self.denied_events.append({"method": method, "params": message.get("params")})
            self._respond(message.get("id"), {"answers": {}})
        else:
            # Unknown server request: decline rather than guess at its contract.
            self._respond(message.get("id"), {})

    def _handle_notification(self, message: dict[str, Any]) -> None:
        # Streaming fragments repeat what item/completed carries whole. Keeping them made
        # every saved run record roughly ten times larger.
        if not str(message.get("method", "")).endswith(("/delta", "Delta")):
            self.notifications.append(message)
        if self.on_notification is not None:
            self.on_notification(message)

    def request(self, method: str, params: Any = None) -> dict[str, Any]:
        with self._lock:
            return self._exchange(method, params)

    def _exchange(self, method: str, params: Any = None) -> dict[str, Any]:
        """Send one request and read until its response. Callers hold ``_lock``."""
        transport = self._ensure_transport()
        request_id = self._send_request(method, params)

        while True:
            line = transport.readline()
            if not line:
                raise GenerationError(f"Codex app server disconnected during {method}")
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                raise GenerationError("Codex app server returned invalid JSON") from exc

            if "method" in message and "id" in message:
                self._handle_server_request(message)
                continue
            if "method" in message:
                self._handle_notification(message)
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                detail = (message["error"] or {}).get("message", "unknown error")
                raise GenerationError(f"Codex {method} failed: {detail}")
            return message.get("result") or {}

    # -- Lifecycle ---------------------------------------------------------

    def connect(self) -> dict[str, Any]:
        result = self.request(
            "initialize",
            {"clientInfo": {"name": CLIENT_NAME, "title": "AlephTav", "version": CLIENT_VERSION}},
        )
        self.initialized = True
        return result

    def account(self, refresh_token: bool = False) -> dict[str, Any]:
        return self.request("account/read", {"refreshToken": refresh_token})

    def list_models(self) -> list[dict[str, Any]]:
        result = self.request("model/list", {})
        items = result.get("data") or []
        return [item for item in items if isinstance(item, dict)]

    def default_model(self) -> str | None:
        """The model this account defaults to, read once and kept for the process."""
        if self._default_model is None:
            models = self.list_models()
            chosen = next(
                (item for item in models if item.get("isDefault")),
                models[0] if models else None,
            )
            self._default_model = str((chosen or {}).get("id") or "")
        return self._default_model or None

    def login(self) -> dict[str, Any]:
        """Start Codex's own managed sign-in. AlephTav never sees the tokens."""
        return self.request("account/login/start", {})

    def rate_limits(self) -> dict[str, Any]:
        return self.request("account/rateLimits/read", None)

    # -- Threads and turns -------------------------------------------------

    def start_thread(self, base_instructions: str | None = None) -> str:
        """Open a Codex thread locked to text generation.

        The sandbox is read-only and approvals are routed back to this client,
        which denies them, so a translation turn cannot change the machine.
        """
        params: dict[str, Any] = {
            "sandbox": "read-only",
            "approvalPolicy": "on-request",
        }
        if base_instructions:
            params["baseInstructions"] = base_instructions
        result = self.request("thread/start", params)
        thread_id = (result.get("thread") or {}).get("id")
        if not thread_id:
            raise GenerationError("Codex thread/start did not return a threadId")
        self._threads.add(str(thread_id))
        return str(thread_id)

    def resume_thread(self, thread_id: str) -> dict[str, Any]:
        result = self.request("thread/resume", {"threadId": thread_id})
        self._threads.add(thread_id)
        return result

    def _pump_until_turn_complete(self, turn_id: str | None) -> dict[str, Any]:
        """Read notifications until the turn finishes, collecting its output."""
        transport = self._ensure_transport()
        text_parts: list[str] = []
        while True:
            line = transport.readline()
            self._last_message_at = time.monotonic()
            if not line:
                raise GenerationError("Codex app server disconnected during turn")
            line = line.strip()
            if not line:
                continue
            message = json.loads(line)
            if "method" in message and "id" in message:
                self._handle_server_request(message)
                continue
            if "method" not in message:
                continue
            self._handle_notification(message)
            method = message["method"]
            params = message.get("params") or {}
            if method == "item/agentMessage/delta" and isinstance(params.get("delta"), str):
                # Measured so the watchdog can tell a long answer from a runaway one.
                self._streamed_chars += len(params["delta"])
                self._stream_tail = (self._stream_tail + params["delta"])[-self.blank_run_chars :]
            if method == "error":
                if params.get("willRetry"):
                    continue
                error = params.get("error") or {}
                raise GenerationError(str(error.get("message") or "Codex reported an error"))
            if method == "item/completed":
                item = params.get("item") or {}
                # Commentary posted between tool calls is not the answer; only the final
                # message follows the output contract.
                if (
                    item.get("type") == "agentMessage"
                    and item.get("text")
                    and item.get("phase") != "commentary"
                ):
                    text_parts.append(str(item["text"]))
            if method == "turn/completed":
                turn = params.get("turn") or {}
                if turn_id and str(turn.get("id")) != turn_id:
                    continue
                if turn.get("status") == "interrupted":
                    raise GenerationError(self._stop_reason or "Stopped before Codex finished")
                if turn.get("status") == "failed":
                    error = turn.get("error") or {}
                    raise GenerationError(str(error.get("message") or "Codex turn failed"))
                usage = params.get("usage") or turn.get("usage") or {}
                return {"text": "".join(text_parts), "usage": usage, "turn": turn}

    def run_turn(
        self,
        thread_id: str,
        text: str,
        output_schema: dict[str, Any] | None = None,
        model: str | None = None,
        effort: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "threadId": thread_id,
            "input": [{"type": "text", "text": text}],
            "sandboxPolicy": {"type": "readOnly"},
            "approvalPolicy": "on-request",
        }
        if output_schema is not None:
            params["outputSchema"] = output_schema
        if model:
            params["model"] = model
        if effort:
            params["effort"] = effort
        # Hold the transport for the whole turn so no other request reads its notifications.
        with self._lock:
            if thread_id not in self._threads:
                # Saved before AlephTav restarted: this app server has never loaded it.
                self._exchange("thread/resume", {"threadId": thread_id})
                self._threads.add(thread_id)
            started = self._exchange("turn/start", params)
            turn_id = (started.get("turn") or {}).get("id")
            self.active_turn = (thread_id, str(turn_id)) if turn_id else None
            self._last_message_at = self._turn_started_at = time.monotonic()
            self._streamed_chars = 0
            self._stream_tail = ""
            self._stop_reason = None
            done = threading.Event()
            if turn_id:
                threading.Thread(
                    target=self._watch_for_stall,
                    args=(thread_id, str(turn_id), done),
                    daemon=True,
                ).start()
            try:
                result = self._pump_until_turn_complete(str(turn_id) if turn_id else None)
            finally:
                done.set()
                self.active_turn = None
        result["turn_id"] = turn_id
        return result

    def _runaway_reason(self) -> str | None:
        """Why the turn in flight should be stopped, if it should."""
        now = time.monotonic()
        if now - self._last_message_at > self.stall_timeout:
            minutes = round(self.stall_timeout / 60)
            return (
                f"Codex stopped responding for {minutes} minutes, so the turn was stopped. "
                "This is usually a stalled connection to the model; try again."
            )
        if len(self._stream_tail) >= self.blank_run_chars and not self._stream_tail.strip():
            return (
                "Codex's answer turned into endless blank space, so the turn was stopped. "
                "Models sometimes fail this way when held to a strict JSON format; try again."
            )
        if self._streamed_chars > self.max_answer_chars:
            return (
                f"Codex's answer passed {self.max_answer_chars:,} characters without "
                "finishing, so the turn was stopped. The answer ran away; try again."
            )
        if now - self._turn_started_at > self.turn_timeout:
            minutes = round(self.turn_timeout / 60)
            return (
                f"Codex was still working after {minutes} minutes, so the turn was stopped. "
                "Healthy turns finish in a few minutes; try again, perhaps with fewer verses."
            )
        return None

    def _watch_for_stall(self, thread_id: str, turn_id: str, done: threading.Event) -> None:
        """Interrupt a silent or runaway turn; the pumping thread then reports why."""
        interval = min(15.0, self.stall_timeout / 4, self.turn_timeout / 4)
        while not done.wait(interval):
            reason = self._runaway_reason()
            if reason:
                self._stop_reason = reason
                self.interrupt(thread_id, turn_id)
                return

    def interrupt(self, thread_id: str, turn_id: str) -> None:
        """Ask Codex to stop a turn without waiting for the transport.

        The thread pumping that turn holds ``_lock``, so this only writes the request;
        that thread reads the reply and the turn's completion, marked interrupted.
        """
        self._send_request("turn/interrupt", {"threadId": thread_id, "turnId": turn_id})

    def close(self) -> None:
        if self.transport is not None:
            self.transport.close()
            self.transport = None
        self.initialized = False
        self._threads.clear()


_ACTIVE_CLIENT: CodexAppServerClient | None = None


def active_client() -> CodexAppServerClient | None:
    """The managed client, if one has been connected."""
    return _ACTIVE_CLIENT


def connect() -> CodexAppServerClient:
    """Start and initialise the managed app server (idempotent)."""
    global _ACTIVE_CLIENT
    if _ACTIVE_CLIENT is None or not _ACTIVE_CLIENT.initialized:
        if codex_executable() is None:
            raise GenerationError("Codex executable not found on PATH")
        client = CodexAppServerClient()
        client.connect()
        _ACTIVE_CLIENT = client
    return _ACTIVE_CLIENT


def require_client() -> CodexAppServerClient:
    if _ACTIVE_CLIENT is None or not _ACTIVE_CLIENT.initialized:
        raise GenerationError("Codex is not connected. Connect to the local app server first.")
    return _ACTIVE_CLIENT


def set_active_client(client: CodexAppServerClient | None) -> None:
    """Injection point for tests; production goes through :func:`connect`."""
    global _ACTIVE_CLIENT
    _ACTIVE_CLIENT = client


def shutdown() -> None:
    """Terminate the managed subprocess when AlephTav stops (FR-1)."""
    global _ACTIVE_CLIENT
    if _ACTIVE_CLIENT is not None:
        _ACTIVE_CLIENT.close()
        _ACTIVE_CLIENT = None


def _account_details(account: dict[str, Any]) -> dict[str, Any]:
    """Auth mode and plan from an ``account/read`` result.

    The live app server nests these under ``account``
    (``{"account": {"type": "chatgpt", "planType": "pro"}}``); flat keys are
    tolerated so a differently shaped build still reports something.
    """
    nested = account.get("account")
    nested = nested if isinstance(nested, dict) else {}
    return {
        "auth_mode": nested.get("type") or account.get("authMode") or account.get("auth_mode"),
        "plan_type": nested.get("planType")
        or nested.get("plan_type")
        or account.get("planType")
        or account.get("plan_type"),
    }


def _is_signed_in(account: dict[str, Any]) -> bool:
    if not account:
        return False
    for key in ("authenticated", "signedIn", "isSignedIn"):
        if key in account:
            return bool(account[key])
    # Signed out returns a null/absent account object.
    return bool(account.get("account") or account.get("authMode") or account.get("planType"))


def describe_status(client: CodexAppServerClient | None = None) -> dict[str, Any]:
    """Local provider status for the settings panel (FR-1, FR-2).

    Never includes tokens or any credential material.
    """
    if codex_executable() is None and (client is None or client.transport is None):
        return {
            "provider": PROVIDER_NAME,
            "status": STATUS_NOT_INSTALLED,
            "detail": "The codex executable was not found on PATH.",
            "local_only": True,
        }
    if client is None or not client.initialized:
        return {
            "provider": PROVIDER_NAME,
            "status": STATUS_AVAILABLE,
            "detail": "Codex is installed. Connect to start the local app server.",
            "local_only": True,
        }
    if client.active_turn is not None:
        # Asking for the account would queue behind the turn, so the status check
        # itself would hang for as long as the turn runs.
        return {
            "provider": PROVIDER_NAME,
            "status": STATUS_BUSY,
            "detail": "Codex is running a turn.",
            "local_only": True,
        }
    try:
        account = client.account()
    except GenerationError as error:
        return {
            "provider": PROVIDER_NAME,
            "status": STATUS_ERROR,
            "detail": str(error),
            "local_only": True,
        }
    if not _is_signed_in(account):
        return {
            "provider": PROVIDER_NAME,
            "status": STATUS_NOT_SIGNED_IN,
            "detail": "Sign in with ChatGPT through Codex to continue.",
            "local_only": True,
        }
    return {
        "provider": PROVIDER_NAME,
        "status": STATUS_READY,
        "detail": "Connected to the local Codex app server.",
        "local_only": True,
        # Only mode and plan; the account record also carries an email, which
        # the panel has no need for.
        **_account_details(account),
    }
