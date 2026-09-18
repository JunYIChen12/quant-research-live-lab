"""Small, fail-closed supervisor for one local Freqtrade Dry-run round."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .release import ReleaseVerification

REQUEST_TIMEOUT_SECONDS = 5.0
POLL_INTERVAL_SECONDS = 2.0
STARTUP_CONFIRMATION_SECONDS = 60
CLOSING_RECONCILIATION_SECONDS = 300
GET_MAX_RETRIES = 3
GET_BACKOFF_SECONDS = (1.0, 2.0, 4.0)

_DECIMAL_RE = re.compile(r"(?:\d+(?:\.\d+)?|\.\d+)")
_INTEGER_RE = re.compile(r"\d+")
_UTC_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"


class RoundState(StrEnum):
    APPROVAL_PENDING = "APPROVAL_PENDING"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    WAITING_FOR_STRATEGY = "WAITING_FOR_STRATEGY"
    CLOSING = "CLOSING"
    RECONCILING = "RECONCILING"
    COMPLETED_TARGET = "COMPLETED_TARGET"
    COMPLETED_TIMEOUT = "COMPLETED_TIMEOUT"
    STOPPED_USER = "STOPPED_USER"
    STOPPED_LOSS_LOCK = "STOPPED_LOSS_LOCK"
    BLOCKED = "BLOCKED"


TERMINAL_STATES = frozenset(
    {
        RoundState.COMPLETED_TARGET,
        RoundState.COMPLETED_TIMEOUT,
        RoundState.STOPPED_USER,
        RoundState.STOPPED_LOSS_LOCK,
        RoundState.BLOCKED,
    }
)


class ActionStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    UNKNOWN = "UNKNOWN"
    COMPLETED = "COMPLETED"


class StateConflict(RuntimeError):
    """The requested transition would violate the one-round contract."""


class ReconciliationError(RuntimeError):
    """A Freqtrade snapshot cannot be safely attributed to this round."""


class RestError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, uncertain: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.uncertain = uncertain


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _decimal_input(value: object, field: str) -> Decimal:
    if not isinstance(value, str) or not _DECIMAL_RE.fullmatch(value):
        raise ValueError(f"{field} must be a finite decimal string without exponent")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field} is not a decimal") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return parsed


def _decimal_value(value: object, field: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field} is not a decimal")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field} must be finite")
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} is not a decimal") from exc
    if not parsed.is_finite() or (positive and parsed <= 0) or (not positive and parsed < 0):
        comparator = "greater than zero" if positive else "non-negative"
        raise ValueError(f"{field} must be finite and {comparator}")
    return parsed


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _minutes_input(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("duration_minutes must be a positive integer")
    if isinstance(value, int):
        minutes = value
    elif isinstance(value, str) and _INTEGER_RE.fullmatch(value):
        minutes = int(value)
    else:
        raise ValueError("duration_minutes must be a positive integer")
    if minutes <= 0 or minutes > (2**63 - 1) // 60:
        raise ValueError("duration_minutes is outside the supported range")
    return minutes


@dataclass(frozen=True, slots=True)
class RoundInputs:
    capital: Decimal
    target_profit: Decimal
    duration_seconds: int
    max_loss: Decimal
    stake_currency: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.capital, Decimal)
            or not self.capital.is_finite()
            or self.capital <= 0
        ):
            raise ValueError("capital must be a positive Decimal")
        if (
            not isinstance(self.target_profit, Decimal)
            or not self.target_profit.is_finite()
            or self.target_profit <= 0
        ):
            raise ValueError("target_profit must be a positive Decimal")
        if not isinstance(self.duration_seconds, int) or self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if (
            not isinstance(self.max_loss, Decimal)
            or not self.max_loss.is_finite()
            or self.max_loss <= 0
        ):
            raise ValueError("max_loss must be a positive Decimal")
        if self.max_loss > self.capital:
            raise ValueError("max_loss cannot exceed capital")
        if not isinstance(self.stake_currency, str) or not self.stake_currency.strip():
            raise ValueError("stake_currency is required")

    @property
    def principal(self) -> Decimal:
        return self.capital

    @classmethod
    def from_strings(
        cls,
        *,
        capital: str,
        target_profit: str,
        duration_minutes: str,
        max_loss: str,
        stake_currency: str,
        dry_run_wallet: object,
    ) -> RoundInputs:
        parsed_capital = _decimal_input(capital, "capital")
        parsed_target = _decimal_input(target_profit, "target_profit")
        parsed_loss = _decimal_input(max_loss, "max_loss")
        if parsed_loss > parsed_capital:
            raise ValueError("max_loss cannot exceed capital")
        wallet = _decimal_value(dry_run_wallet, "dry_run_wallet", positive=True)
        if wallet != parsed_capital:
            raise ValueError("capital must exactly match dry_run_wallet")
        return cls(
            capital=parsed_capital,
            target_profit=parsed_target,
            duration_seconds=_minutes_input(duration_minutes) * 60,
            max_loss=parsed_loss,
            stake_currency=stake_currency,
        )

    @classmethod
    def from_user_input(cls, **kwargs: object) -> RoundInputs:
        return cls.from_strings(**kwargs)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class RiskConfig:
    exit_cost_buffer_bps: Decimal

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> RiskConfig:
        if "exit_cost_buffer_bps" not in raw:
            raise ValueError("risk_config.exit_cost_buffer_bps is required")
        return cls(_decimal_value(raw["exit_cost_buffer_bps"], "exit_cost_buffer_bps"))

    @classmethod
    def from_toml(cls, path: Path) -> RiskConfig:
        import tomllib

        with path.open("rb") as handle:
            raw = tomllib.load(handle)
        if isinstance(raw.get("risk_config"), Mapping):
            raw = raw["risk_config"]
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class FreqtradeSnapshot:
    health: Mapping[str, object]
    config: Mapping[str, object]
    open_trades: tuple[Mapping[str, object], ...]
    closed_trades: tuple[Mapping[str, object], ...]
    balance: Decimal
    observed_at: datetime
    market_data_reliable: bool = True
    qualifying_strategy: bool = True
    open_orders: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        if not self.health or not isinstance(self.config, Mapping):
            raise ReconciliationError("health_or_config_unavailable")
        if not self.balance.is_finite():
            raise ReconciliationError("balance_invalid")

    @property
    def all_open_orders(self) -> tuple[Mapping[str, object], ...]:
        found = list(self.open_orders)
        for trade in self.open_trades:
            orders = trade.get("orders", ())
            if not isinstance(orders, Sequence) or isinstance(orders, (str, bytes)):
                raise ReconciliationError("orders_invalid")
            found.extend(
                order
                for order in orders
                if isinstance(order, Mapping) and bool(order.get("is_open"))
            )
        return tuple(found)

    @property
    def has_open_orders(self) -> bool:
        return bool(self.all_open_orders)


@dataclass(frozen=True, slots=True)
class RoundRecord:
    round_id: str
    release_id: str
    approved_commit_sha: str
    stake_currency: str
    capital: Decimal
    target_profit: Decimal
    duration_seconds: int
    max_loss: Decimal
    state: RoundState
    start_trade_id_max: int | None
    started_at_utc: datetime | None
    starting_balance: Decimal | None
    elapsed_seconds: int
    timer_anchor_utc: datetime | None
    loss_lock: bool
    user_stop_requested: bool
    stop_reason: str | None
    pending_action_id: str | None
    last_observation_at: datetime | None
    updated_at: datetime
    terminal: bool
    last_estimated_net: Decimal | None
    last_realized_net: Decimal | None
    last_balance: Decimal | None
    startup_deadline_utc: datetime | None
    strategy_name: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "round_id": self.round_id,
            "release_id": self.release_id,
            "approved_commit_sha": self.approved_commit_sha,
            "stake_currency": self.stake_currency,
            "capital": _decimal_text(self.capital),
            "target_profit": _decimal_text(self.target_profit),
            "duration_seconds": self.duration_seconds,
            "max_loss": _decimal_text(self.max_loss),
            "state": self.state.value,
            "start_trade_id_max": self.start_trade_id_max,
            "started_at_utc": _format_time(self.started_at_utc),
            "starting_balance": _decimal_text(self.starting_balance)
            if self.starting_balance is not None
            else None,
            "elapsed_seconds": self.elapsed_seconds,
            "loss_lock": self.loss_lock,
            "user_stop_requested": self.user_stop_requested,
            "stop_reason": self.stop_reason,
            "pending_action_id": self.pending_action_id,
            "last_observation_at": _format_time(self.last_observation_at),
            "updated_at": _format_time(self.updated_at),
            "last_estimated_net": _decimal_text(self.last_estimated_net)
            if self.last_estimated_net is not None
            else None,
            "last_realized_net": _decimal_text(self.last_realized_net)
            if self.last_realized_net is not None
            else None,
            "last_balance": (
                _decimal_text(self.last_balance) if self.last_balance is not None else None
            ),
            "strategy_name": self.strategy_name,
        }


@dataclass(frozen=True, slots=True)
class ActionRecord:
    action_id: str
    round_id: str
    action_type: str
    expected_state: str
    status: ActionStatus
    created_at: datetime
    updated_at: datetime
    request_count: int


def _format_time(value: datetime | None) -> str | None:
    return value.astimezone(UTC).strftime(_UTC_FORMAT) if value else None


def _parse_time(value: str | None) -> datetime | None:
    return datetime.strptime(value, _UTC_FORMAT) if value else None


class SQLiteStateStore:
    """Persist only round supervision and audit summaries, never trade facts."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS rounds (
                round_id TEXT PRIMARY KEY,
                release_id TEXT NOT NULL,
                approved_commit_sha TEXT NOT NULL,
                stake_currency TEXT NOT NULL,
                capital TEXT NOT NULL,
                target_profit TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL,
                max_loss TEXT NOT NULL,
                state TEXT NOT NULL,
                start_trade_id_max INTEGER,
                started_at_utc TEXT,
                starting_balance TEXT,
                elapsed_seconds INTEGER NOT NULL DEFAULT 0,
                timer_anchor_utc TEXT,
                loss_lock INTEGER NOT NULL DEFAULT 0,
                user_stop_requested INTEGER NOT NULL DEFAULT 0,
                stop_reason TEXT,
                pending_action_id TEXT,
                last_observation_at TEXT,
                updated_at TEXT NOT NULL,
                terminal INTEGER NOT NULL DEFAULT 0,
                last_estimated_net TEXT,
                last_realized_net TEXT,
                last_balance TEXT,
                startup_deadline_utc TEXT,
                strategy_name TEXT,
                parameter_update_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS actions (
                action_id TEXT PRIMARY KEY,
                round_id TEXT NOT NULL REFERENCES rounds(round_id),
                action_type TEXT NOT NULL,
                expected_state TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                request_count INTEGER NOT NULL DEFAULT 0,
                UNIQUE(round_id, action_type)
            );
            CREATE TABLE IF NOT EXISTS observations (
                observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id TEXT NOT NULL REFERENCES rounds(round_id),
                observed_at TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                status_code INTEGER,
                summary_sha256 TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id TEXT NOT NULL REFERENCES rounds(round_id),
                created_at TEXT NOT NULL,
                reason TEXT NOT NULL,
                details_json TEXT NOT NULL
            );
            """
        )
        columns = {
            row[1] for row in self.connection.execute("PRAGMA table_info(rounds)").fetchall()
        }
        if "parameter_update_count" not in columns:
            self.connection.execute(
                "ALTER TABLE rounds ADD COLUMN parameter_update_count INTEGER NOT NULL DEFAULT 0"
            )
        self.connection.commit()
        self._lock = threading.RLock()

    @contextmanager
    def _transaction(self):
        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                yield
            except Exception:
                self.connection.rollback()
                raise
            else:
                self.connection.commit()

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    def create_round(
        self,
        inputs: RoundInputs,
        *,
        release_id: str,
        approved_commit_sha: str,
        strategy_name: str | None = None,
        round_id: str | None = None,
        now: datetime | None = None,
    ) -> RoundRecord:
        round_id = round_id or f"round-{uuid.uuid4().hex}"
        timestamp = _format_time(now or _utc_now())
        with self._transaction():
            active = self.connection.execute(
                "SELECT round_id FROM rounds WHERE terminal = 0 LIMIT 1"
            ).fetchone()
            if active:
                raise StateConflict("an active round already exists")
            try:
                self.connection.execute(
                    """
                    INSERT INTO rounds (
                        round_id, release_id, approved_commit_sha, stake_currency,
                        capital, target_profit, duration_seconds, max_loss, state,
                        updated_at, strategy_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        round_id,
                        release_id,
                        approved_commit_sha,
                        inputs.stake_currency,
                        _decimal_text(inputs.capital),
                        _decimal_text(inputs.target_profit),
                        inputs.duration_seconds,
                        _decimal_text(inputs.max_loss),
                        RoundState.APPROVAL_PENDING.value,
                        timestamp,
                        strategy_name,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise StateConflict("round_id already exists") from exc
        return self.get_round(round_id)  # type: ignore[return-value]

    def current_round(self) -> RoundRecord | None:
        row = self.connection.execute(
            "SELECT * FROM rounds ORDER BY updated_at DESC, rowid DESC LIMIT 1"
        ).fetchone()
        return _round_from_row(row) if row else None

    def get_round(self, round_id: str) -> RoundRecord | None:
        row = self.connection.execute(
            "SELECT * FROM rounds WHERE round_id = ?", (round_id,)
        ).fetchone()
        return _round_from_row(row) if row else None

    def update_round(self, round_id: str, **fields: object) -> RoundRecord:
        allowed = {
            "state",
            "start_trade_id_max",
            "started_at_utc",
            "starting_balance",
            "elapsed_seconds",
            "timer_anchor_utc",
            "loss_lock",
            "user_stop_requested",
            "stop_reason",
            "pending_action_id",
            "last_observation_at",
            "updated_at",
            "terminal",
            "last_estimated_net",
            "last_realized_net",
            "last_balance",
            "startup_deadline_utc",
            "target_profit",
            "duration_seconds",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"unsupported round fields: {sorted(unknown)}")
        fields.setdefault("updated_at", _format_time(_utc_now()))
        assignments = ", ".join(f"{name} = ?" for name in fields)
        with self._transaction():
            result = self.connection.execute(
                f"UPDATE rounds SET {assignments} WHERE round_id = ?",
                (*fields.values(), round_id),
            )
            if result.rowcount != 1:
                raise StateConflict("round does not exist")
        return self.get_round(round_id)  # type: ignore[return-value]

    def update_parameters(
        self,
        round_id: str,
        *,
        target_profit: Decimal,
        duration_seconds: int,
        now: datetime | None = None,
    ) -> RoundRecord:
        with self._transaction():
            row = self.connection.execute(
                "SELECT state, parameter_update_count FROM rounds WHERE round_id = ?",
                (round_id,),
            ).fetchone()
            if not row:
                raise StateConflict("round does not exist")
            if row["state"] not in {
                RoundState.RUNNING.value,
                RoundState.WAITING_FOR_STRATEGY.value,
            }:
                raise StateConflict("target and duration are frozen outside RUNNING")
            if int(row["parameter_update_count"]) >= 1:
                raise StateConflict("target and duration may only be updated once")
            result = self.connection.execute(
                "UPDATE rounds SET target_profit = ?, duration_seconds = ?, updated_at = ?, "
                "parameter_update_count = parameter_update_count + 1 "
                "WHERE round_id = ? AND parameter_update_count = 0",
                (
                    _decimal_text(target_profit),
                    duration_seconds,
                    _format_time(now or _utc_now()),
                    round_id,
                ),
            )
            if result.rowcount != 1:
                raise StateConflict("target and duration may only be updated once")
        return self.get_round(round_id)  # type: ignore[return-value]

    def ensure_action(
        self,
        round_id: str,
        action_type: str,
        expected_state: RoundState | str,
        *,
        now: datetime | None = None,
    ) -> ActionRecord:
        timestamp = _format_time(now or _utc_now())
        with self._transaction():
            row = self.connection.execute(
                "SELECT * FROM actions WHERE round_id = ? AND action_type = ?",
                (round_id, action_type),
            ).fetchone()
            if not row:
                self.connection.execute(
                    """
                    INSERT INTO actions (
                        action_id, round_id, action_type, expected_state, status,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"action-{uuid.uuid4().hex}",
                        round_id,
                        action_type,
                        str(expected_state),
                        ActionStatus.PENDING.value,
                        timestamp,
                        timestamp,
                    ),
                )
                row = self.connection.execute(
                    "SELECT * FROM actions WHERE round_id = ? AND action_type = ?",
                    (round_id, action_type),
                ).fetchone()
        return _action_from_row(row)  # type: ignore[arg-type]

    def get_action(self, round_id: str, action_type: str) -> ActionRecord | None:
        row = self.connection.execute(
            "SELECT * FROM actions WHERE round_id = ? AND action_type = ?",
            (round_id, action_type),
        ).fetchone()
        return _action_from_row(row) if row else None

    def get_action_by_id(self, action_id: str) -> ActionRecord | None:
        row = self.connection.execute(
            "SELECT * FROM actions WHERE action_id = ?", (action_id,)
        ).fetchone()
        return _action_from_row(row) if row else None

    def mark_action(
        self,
        action_id: str,
        status: ActionStatus,
        *,
        increment_request: bool = False,
        now: datetime | None = None,
    ) -> ActionRecord:
        timestamp = _format_time(now or _utc_now())
        increment = "request_count = request_count + 1," if increment_request else ""
        with self._transaction():
            result = self.connection.execute(
                f"UPDATE actions SET status = ?, {increment} updated_at = ? WHERE action_id = ?",
                (status.value, timestamp, action_id),
            )
            if result.rowcount != 1:
                raise StateConflict("action does not exist")
        row = self.connection.execute(
            "SELECT * FROM actions WHERE action_id = ?", (action_id,)
        ).fetchone()
        return _action_from_row(row)  # type: ignore[arg-type]

    def record_observation(
        self,
        round_id: str,
        endpoint: str,
        *,
        status_code: int | None,
        summary: object,
        observed_at: datetime | None = None,
    ) -> None:
        summary_hash = hashlib.sha256(
            json.dumps(summary, sort_keys=True, default=str, ensure_ascii=True).encode()
        ).hexdigest()
        with self._transaction():
            self.connection.execute(
                "INSERT INTO observations "
                "(round_id, observed_at, endpoint, status_code, summary_sha256) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    round_id,
                    _format_time(observed_at or _utc_now()),
                    endpoint,
                    status_code,
                    summary_hash,
                ),
            )

    def record_event(
        self,
        round_id: str,
        reason: str,
        details: Mapping[str, object] | None = None,
        *,
        created_at: datetime | None = None,
    ) -> None:
        with self._transaction():
            self.connection.execute(
                "INSERT INTO events "
                "(round_id, created_at, reason, details_json) VALUES (?, ?, ?, ?)",
                (
                    round_id,
                    _format_time(created_at or _utc_now()),
                    reason,
                    json.dumps(details or {}, sort_keys=True, ensure_ascii=True, default=str),
                ),
            )

    def events(self, round_id: str) -> list[dict[str, object]]:
        rows = self.connection.execute(
            "SELECT reason, details_json, created_at FROM events "
            "WHERE round_id = ? ORDER BY event_id",
            (round_id,),
        ).fetchall()
        return [
            {
                "reason": row["reason"],
                "details": json.loads(row["details_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]


def _round_from_row(row: sqlite3.Row) -> RoundRecord:
    def decimal_or_none(name: str) -> Decimal | None:
        return Decimal(row[name]) if row[name] is not None else None

    return RoundRecord(
        round_id=row["round_id"],
        release_id=row["release_id"],
        approved_commit_sha=row["approved_commit_sha"],
        stake_currency=row["stake_currency"],
        capital=Decimal(row["capital"]),
        target_profit=Decimal(row["target_profit"]),
        duration_seconds=int(row["duration_seconds"]),
        max_loss=Decimal(row["max_loss"]),
        state=RoundState(row["state"]),
        start_trade_id_max=row["start_trade_id_max"],
        started_at_utc=_parse_time(row["started_at_utc"]),
        starting_balance=decimal_or_none("starting_balance"),
        elapsed_seconds=int(row["elapsed_seconds"]),
        timer_anchor_utc=_parse_time(row["timer_anchor_utc"]),
        loss_lock=bool(row["loss_lock"]),
        user_stop_requested=bool(row["user_stop_requested"]),
        stop_reason=row["stop_reason"],
        pending_action_id=row["pending_action_id"],
        last_observation_at=_parse_time(row["last_observation_at"]),
        updated_at=_parse_time(row["updated_at"]) or _utc_now(),
        terminal=bool(row["terminal"]),
        last_estimated_net=decimal_or_none("last_estimated_net"),
        last_realized_net=decimal_or_none("last_realized_net"),
        last_balance=decimal_or_none("last_balance"),
        startup_deadline_utc=_parse_time(row["startup_deadline_utc"]),
        strategy_name=row["strategy_name"],
    )


def _action_from_row(row: sqlite3.Row) -> ActionRecord:
    return ActionRecord(
        action_id=row["action_id"],
        round_id=row["round_id"],
        action_type=row["action_type"],
        expected_state=row["expected_state"],
        status=ActionStatus(row["status"]),
        created_at=_parse_time(row["created_at"]) or _utc_now(),
        updated_at=_parse_time(row["updated_at"]) or _utc_now(),
        request_count=int(row["request_count"]),
    )


class FreqtradeRestClient:
    """Small REST boundary; only GET retries and credentials stay in memory."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
        max_get_retries: int = GET_MAX_RETRIES,
        opener: Callable[..., Any] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        observation_sink: Callable[[str, int | None, object], None] | None = None,
    ) -> None:
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("FREQTRADE_API_URL must be an HTTP(S) URL")
        if parsed.username or parsed.password:
            raise ValueError("FREQTRADE_API_URL must not contain credentials")
        if not username or not password:
            raise ValueError("runtime API credentials are required")
        if timeout_seconds <= 0 or max_get_retries < 0:
            raise ValueError("invalid REST budget")
        self.base_url = base_url.rstrip("/")
        self._auth = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        self.timeout_seconds = timeout_seconds
        self.max_get_retries = max_get_retries
        self._opener = opener or urllib.request.urlopen
        self._sleeper = sleeper
        self.observation_sink = observation_sink

    @classmethod
    def from_environment(
        cls,
        *,
        environ: Mapping[str, str] | None = None,
        **kwargs: object,
    ) -> FreqtradeRestClient:
        source = os.environ if environ is None else environ
        return cls(
            source.get("FREQTRADE_API_URL", ""),
            source.get("FREQTRADE_API_USERNAME", ""),
            source.get("FREQTRADE_API_PASSWORD", ""),
            **kwargs,
        )  # type: ignore[arg-type]

    def __repr__(self) -> str:
        return f"FreqtradeRestClient(base_url={self.base_url!r})"

    def get(self, path: str, *, query: Mapping[str, object] | None = None) -> object:
        return self._request("GET", path, query=query)

    def post(self, path: str, payload: Mapping[str, object] | None = None) -> object:
        return self._request("POST", path, payload=payload)

    def delete(self, path: str) -> object:
        return self._request("DELETE", path)

    def start(self) -> object:
        return self.post("/api/v1/start")

    def pause(self) -> object:
        return self.post("/api/v1/pause")

    def force_exit_all(self) -> object:
        return self.post("/api/v1/forceexit", {"tradeid": "all"})

    def _observe(self, endpoint: str, status_code: int | None, summary: object) -> None:
        if self.observation_sink is None:
            return
        try:
            self.observation_sink(endpoint, status_code, summary)
        except Exception:
            return

    def snapshot(self) -> FreqtradeSnapshot:
        health = self.get("/api/v1/health")
        config = self.get("/api/v1/show_config")
        statuses = self.get("/api/v1/status")
        history = self._all_trades()
        balance = self.get("/api/v1/balance")
        if not isinstance(health, Mapping) or not isinstance(config, Mapping):
            raise ReconciliationError("health_or_config_invalid")
        open_trades = _mapping_sequence(statuses, "status")
        closed_trades = _mapping_sequence(history, "trades")
        if not isinstance(balance, Mapping):
            raise ReconciliationError("balance_invalid")
        raw_balance = balance.get("total_bot", balance.get("total"))
        return FreqtradeSnapshot(
            health=health,
            config=config,
            open_trades=tuple(open_trades),
            closed_trades=tuple(closed_trades),
            balance=_decimal_value(raw_balance, "balance", positive=False),
            observed_at=_utc_now(),
        )

    def _all_trades(self) -> object:
        offset = 0
        collected: list[Mapping[str, object]] = []
        while True:
            payload = self.get(
                "/api/v1/trades",
                query={"limit": 500, "offset": offset, "order_by_id": "true"},
            )
            page = _mapping_sequence(payload, "trades")
            collected.extend(page)
            if not isinstance(payload, Mapping):
                break
            total = payload.get("total_trades")
            if not isinstance(total, int) or offset + len(page) >= total or not page:
                break
            offset += len(page)
        return {"trades": collected}

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, object] | None = None,
        payload: Mapping[str, object] | None = None,
    ) -> object:
        if not path.startswith("/") or not path.startswith("/api/"):
            raise ValueError("REST path must be under /api/")
        url = f"{self.base_url}{path}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        body = json.dumps(payload).encode() if payload is not None else None
        attempts = self.max_get_retries + 1 if method == "GET" else 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            request = urllib.request.Request(
                url,
                data=body,
                method=method,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Basic {self._auth}",
                },
            )
            try:
                with self._opener(request, timeout=self.timeout_seconds) as response:
                    status = int(
                        response.getcode() if hasattr(response, "getcode") else response.status
                    )
                    raw = response.read()
                if status < 200 or status >= 300:
                    self._observe(
                        path,
                        status,
                        {
                            "http_ok": False,
                            "payload_sha256": hashlib.sha256(raw).hexdigest(),
                            "payload_bytes": len(raw),
                        },
                    )
                    raise RestError(f"Freqtrade returned HTTP {status}", status_code=status)
                try:
                    result = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    self._observe(
                        path,
                        status,
                        {
                            "http_ok": True,
                            "json_valid": False,
                            "payload_sha256": hashlib.sha256(raw).hexdigest(),
                            "payload_bytes": len(raw),
                        },
                    )
                    raise RestError("Freqtrade returned invalid JSON") from exc
                self._observe(
                    path,
                    status,
                    {
                        "http_ok": True,
                        "json_type": type(result).__name__,
                        "payload_sha256": hashlib.sha256(raw).hexdigest(),
                        "payload_bytes": len(raw),
                    },
                )
                return result
            except urllib.error.HTTPError as exc:
                self._observe(
                    path,
                    exc.code,
                    {"http_ok": False, "error": "http_error"},
                )
                last_error = RestError(f"Freqtrade returned HTTP {exc.code}", status_code=exc.code)
            except (OSError, urllib.error.URLError, TimeoutError, RestError) as exc:
                if not isinstance(exc, RestError):
                    self._observe(
                        path,
                        None,
                        {"http_ok": False, "error": type(exc).__name__},
                    )
                last_error = exc
            if method != "GET" or attempt >= attempts - 1:
                break
            self._sleeper(GET_BACKOFF_SECONDS[min(attempt, len(GET_BACKOFF_SECONDS) - 1)])
        if isinstance(last_error, RestError):
            raise last_error
        raise RestError("Freqtrade request failed", uncertain=method != "GET") from last_error


def _mapping_sequence(value: object, label: str) -> list[Mapping[str, object]]:
    if isinstance(value, Mapping):
        value = value.get(label, [])
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ReconciliationError(f"{label}_invalid")
    if not all(isinstance(item, Mapping) for item in value):
        raise ReconciliationError(f"{label}_invalid")
    return list(value)


def _as_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    return None


def _as_integer(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ReconciliationError(f"{field}_invalid")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        return int(value)
    raise ReconciliationError(f"{field}_invalid")


def _timestamp(value: object, field: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        try:
            seconds = Decimal(str(value))
        except InvalidOperation as exc:
            raise ReconciliationError(f"{field}_invalid") from exc
        if not seconds.is_finite():
            raise ReconciliationError(f"{field}_invalid")
        if seconds > Decimal("100000000000"):
            seconds /= Decimal("1000")
        try:
            return datetime.fromtimestamp(float(seconds), tz=UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise ReconciliationError(f"{field}_invalid") from exc
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return _timestamp(Decimal(text), field)
        except (InvalidOperation, ValueError):
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ReconciliationError(f"{field}_invalid") from exc
            return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    raise ReconciliationError(f"{field}_invalid")


def _trade_id(trade: Mapping[str, object]) -> int:
    raw = trade.get("trade_id", trade.get("id"))
    value = _as_integer(raw, "trade_id")
    if value <= 0:
        raise ReconciliationError("trade_id_invalid")
    return value


def _fill_time(trade: Mapping[str, object]) -> datetime | None:
    for field in (
        "open_fill_timestamp",
        "open_timestamp",
        "open_fill_date",
        "open_date",
        "open_date_utc",
    ):
        value = _timestamp(trade.get(field), field)
        if value is not None:
            return value
    orders = trade.get("orders", ())
    if not isinstance(orders, Sequence) or isinstance(orders, (str, bytes)):
        raise ReconciliationError("orders_invalid")
    for order in orders:
        if not isinstance(order, Mapping):
            raise ReconciliationError("orders_invalid")
        if (
            _as_bool(order.get("ft_is_entry")) is True
            or str(order.get("ft_order_side", "")).lower() == "buy"
        ):
            for field in ("order_filled_timestamp", "order_date", "order_date_utc"):
                value = _timestamp(order.get(field), field)
                if value is not None:
                    return value
    return None


def _open_exit_order(trade: Mapping[str, object]) -> bool:
    orders = trade.get("orders", ())
    if not isinstance(orders, Sequence) or isinstance(orders, (str, bytes)):
        raise ReconciliationError("orders_invalid")
    for order in orders:
        if not isinstance(order, Mapping) or not _as_bool(order.get("is_open")):
            continue
        if _as_bool(order.get("ft_is_entry")) is False:
            return True
        side = str(order.get("ft_order_side", "")).lower()
        if side in {"sell", "close", "exit", "stoploss"}:
            return True
    return False


def _optional_cost(trade: Mapping[str, object], *fields: str) -> Decimal:
    total = Decimal("0")
    for field in fields:
        if field in trade and trade[field] is not None:
            total += _decimal_value(trade[field], field)
    return total


def _signed_decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ReconciliationError(f"{field}_invalid")
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ReconciliationError(f"{field}_invalid") from exc
    if not parsed.is_finite():
        raise ReconciliationError(f"{field}_invalid")
    return parsed


def _trade_profit(trade: Mapping[str, object], *, closed: bool) -> Decimal:
    field = (
        "close_profit_abs" if closed and trade.get("close_profit_abs") is not None else "profit_abs"
    )
    if field not in trade:
        field = "realized_profit" if closed and trade.get("realized_profit") is not None else field
    if field not in trade:
        raise ReconciliationError("profit_invalid")
    value = _signed_decimal(trade[field], field)
    if trade.get("gross_profit_abs") is not None or trade.get("profit_abs_gross") is not None:
        value -= _optional_cost(
            trade, "fee_open_cost", "fee_close_cost", "funding_fees", "interest"
        )
    return value


def _trade_is_open(trade: Mapping[str, object]) -> bool:
    flag = _as_bool(trade.get("is_open"))
    if flag is None:
        raise ReconciliationError("trade_state_invalid")
    return flag


class DryRunSupervisor:
    """Supervise exactly one fail-closed Dry-run round."""

    def __init__(
        self,
        store: SQLiteStateStore,
        client: Any,
        *,
        release_check: Callable[[], ReleaseVerification] | None = None,
        runtime_config: Mapping[str, object] | None = None,
        risk_config: RiskConfig | Mapping[str, object] | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if not isinstance(runtime_config, Mapping):
            raise ValueError("runtime_config is required")
        self.store = store
        self.client = client
        self.release_check = release_check
        self.runtime_config = dict(runtime_config)
        self.clock = clock
        self._lock = threading.RLock()
        self._observation_round_id: str | None = None
        if isinstance(client, FreqtradeRestClient):
            client.observation_sink = self._capture_rest_observation
        self._risk_error: str | None = None
        if isinstance(risk_config, RiskConfig):
            self.risk_config = risk_config
        elif isinstance(risk_config, Mapping):
            try:
                self.risk_config = RiskConfig.from_mapping(risk_config)
            except (TypeError, ValueError) as exc:
                self.risk_config = None
                self._risk_error = str(exc)
        else:
            self.risk_config = None
            self._risk_error = "risk_config_missing"

    def get_round(self, round_id: str) -> RoundRecord:
        record = self.store.get_round(round_id)
        if record is None:
            raise StateConflict("round does not exist")
        return record

    def state_payload(self) -> dict[str, object]:
        record = self.store.current_round()
        if record is None:
            return {"state": None}
        payload = record.as_dict()
        payload.update(
            {
                "can_approve": record.state is RoundState.APPROVAL_PENDING,
                "can_stop": not record.terminal,
                "terminal": record.terminal,
            }
        )
        return payload

    def create_round(
        self,
        inputs: RoundInputs,
        *,
        release_id: str,
        approved_commit_sha: str,
    ) -> RoundRecord:
        with self._lock:
            if not isinstance(inputs, RoundInputs):
                raise ValueError("round inputs are required")
            if not release_id or not approved_commit_sha:
                raise ValueError("release identity is required")
            self._check_input_against_runtime(inputs)
            record = self.store.create_round(
                inputs,
                release_id=release_id,
                approved_commit_sha=approved_commit_sha,
                strategy_name=(
                    str(self.runtime_config["strategy"])
                    if self.runtime_config.get("strategy") is not None
                    else None
                ),
                now=self._now(),
            )
            self.store.record_event(
                record.round_id,
                "round_created",
                {"state": record.state.value},
                created_at=self._now(),
            )
            return record

    def approve_and_start(self, round_id: str) -> RoundRecord:
        with self._lock:
            record = self.get_round(round_id)
            if record.state is not RoundState.APPROVAL_PENDING:
                raise StateConflict("round is not awaiting approval")
            issues = list(self._release_issues(record))
            if self._risk_error:
                issues.append("risk_config_invalid")
            if issues:
                return self._block(record, ";".join(dict.fromkeys(issues)))
            try:
                snapshot = self._snapshot(record)
                issues = self._runtime_issues(snapshot, record, require_empty=True)
                if issues:
                    return self._block(record, ";".join(issues))
                if snapshot.balance != record.capital:
                    return self._block(record, "starting_balance_mismatch")
                boundary = self._max_trade_id(snapshot)
            except ReconciliationError as exc:
                return self._block(record, str(exc))
            now = self._now()
            record = self.store.update_round(
                record.round_id,
                state=RoundState.STARTING.value,
                start_trade_id_max=boundary,
                starting_balance=_decimal_text(snapshot.balance),
                last_balance=_decimal_text(snapshot.balance),
                last_observation_at=_format_time(snapshot.observed_at),
                startup_deadline_utc=_format_time(
                    now + timedelta(seconds=STARTUP_CONFIRMATION_SECONDS)
                ),
                timer_anchor_utc=None,
                stop_reason=None,
                updated_at=_format_time(now),
            )
            start_action = self.store.ensure_action(
                record.round_id, "start", RoundState.STARTING, now=now
            )
            if start_action.status is ActionStatus.PENDING:
                try:
                    self._client_call("start")
                except Exception:
                    self.store.mark_action(
                        start_action.action_id,
                        ActionStatus.UNKNOWN,
                        increment_request=True,
                        now=self._now(),
                    )
                    now = self._now()
                    try:
                        confirmed = self._snapshot(record)
                    except ReconciliationError as reconcile_exc:
                        self._event(
                            record,
                            "start_reconciliation_unavailable",
                            {"reason": str(reconcile_exc)},
                            now,
                        )
                        return self._hold_starting(record, "start_request_uncertain", now)
                    return self._confirm_start(record, confirmed, now)
                self.store.mark_action(
                    start_action.action_id,
                    ActionStatus.SENT,
                    increment_request=True,
                    now=self._now(),
                )
            try:
                confirmed = self._snapshot(record)
            except ReconciliationError as exc:
                return self._block(record, str(exc))
            return self._confirm_start(record, confirmed, self._now())

    def tick(
        self,
        round_id: str | None = None,
        *,
        snapshot: FreqtradeSnapshot | None = None,
        now: datetime | None = None,
    ) -> RoundRecord:
        with self._lock:
            record = self.store.get_round(round_id) if round_id else self.store.current_round()
            if record is None:
                raise StateConflict("round does not exist")
            if record.terminal:
                return record
            current_time = now or self._now()
            if record.state is RoundState.STARTING:
                if record.user_stop_requested:
                    return self._finish(record, RoundState.STOPPED_USER, "user_stop")
                if snapshot is None:
                    try:
                        snapshot = self._snapshot(record)
                    except ReconciliationError as exc:
                        return self._hold_starting(record, str(exc), current_time)
                return self._confirm_start(record, snapshot, current_time)
            if record.state in {RoundState.CLOSING, RoundState.RECONCILING}:
                return self._reconcile(record, snapshot, current_time)
            if snapshot is None:
                try:
                    snapshot = self._snapshot(record)
                except ReconciliationError as exc:
                    return self._block(record, str(exc))
            integrity = list(self._release_issues(record))
            if self._risk_error:
                integrity.append("risk_config_invalid")
            runtime_issues = self._runtime_issues(snapshot, record, require_empty=False)
            integrity.extend(runtime_issues)
            if integrity:
                reasons = list(dict.fromkeys(integrity))
                self._event(record, "observation_rejected", {"reasons": reasons}, current_time)
                if self._has_unprocessed(snapshot):
                    return self._begin_closing(
                        record,
                        RoundState.BLOCKED,
                        "release_integrity:" + ";".join(reasons),
                        snapshot,
                        observed_reasons=reasons,
                        now=current_time,
                    )
                return self._block(record, ";".join(reasons))
            try:
                record = self._update_metrics(record, snapshot, current_time)
                record = self._advance_timer(record, snapshot, current_time)
            except ReconciliationError as exc:
                if self._has_unprocessed(snapshot):
                    return self._begin_closing(
                        record,
                        RoundState.BLOCKED,
                        "reconciliation_error:" + str(exc),
                        snapshot,
                        observed_reasons=[str(exc)],
                        now=current_time,
                    )
                return self._block(record, str(exc))
            reasons: list[str] = []
            if (
                record.last_estimated_net is not None
                and -record.last_estimated_net >= record.max_loss
            ):
                reasons.append("hard_loss")
            if record.user_stop_requested:
                reasons.append("user_stop")
            if record.elapsed_seconds >= record.duration_seconds:
                reasons.append("timeout")
            if (
                record.last_estimated_net is not None
                and record.last_estimated_net >= record.target_profit
            ):
                reasons.append("target_estimate")
            if not snapshot.market_data_reliable or not snapshot.qualifying_strategy:
                reasons.append("waiting_for_strategy")
            if reasons:
                self._event(record, "observed_reasons", {"reasons": reasons}, current_time)
            if "hard_loss" in reasons:
                record = self.store.update_round(
                    record.round_id,
                    loss_lock=1,
                    stop_reason="loss_lock",
                    updated_at=_format_time(current_time),
                )
                return self._begin_closing(
                    record,
                    RoundState.STOPPED_LOSS_LOCK,
                    "loss_lock",
                    snapshot,
                    observed_reasons=reasons,
                    now=current_time,
                )
            if "user_stop" in reasons:
                return self._begin_closing(
                    record,
                    RoundState.STOPPED_USER,
                    "user_stop",
                    snapshot,
                    observed_reasons=reasons,
                    now=current_time,
                )
            if "timeout" in reasons:
                return self._begin_closing(
                    record,
                    RoundState.COMPLETED_TIMEOUT,
                    "timeout",
                    snapshot,
                    observed_reasons=reasons,
                    now=current_time,
                )
            if "target_estimate" in reasons:
                return self._begin_closing(
                    record,
                    RoundState.COMPLETED_TARGET,
                    "target_estimate",
                    snapshot,
                    observed_reasons=reasons,
                    now=current_time,
                )
            if "waiting_for_strategy" in reasons:
                record = self._pause_for_waiting(record, current_time)
                return self.store.update_round(
                    record.round_id,
                    state=RoundState.WAITING_FOR_STRATEGY.value,
                    updated_at=_format_time(current_time),
                )
            if record.state is RoundState.WAITING_FOR_STRATEGY:
                self._event(record, "strategy_recovered", {}, current_time)
            return self.store.update_round(
                record.round_id,
                state=RoundState.RUNNING.value,
                updated_at=_format_time(current_time),
            )

    def request_stop(self, round_id: str | None = None) -> RoundRecord:
        with self._lock:
            record = self.store.get_round(round_id) if round_id else self.store.current_round()
            if record is None:
                raise StateConflict("round does not exist")
            if record.terminal:
                return record
            record = self.store.update_round(
                record.round_id,
                user_stop_requested=1,
                stop_reason="user_stop"
                if record.state is RoundState.APPROVAL_PENDING
                else record.stop_reason,
                updated_at=_format_time(self._now()),
            )
            self._event(record, "user_stop_requested", {}, self._now())
            if record.state is RoundState.APPROVAL_PENDING:
                return self._finish(record, RoundState.STOPPED_USER, "user_stop")
            return self.tick(record.round_id)

    def update_parameters(
        self,
        round_id: str,
        *,
        target_profit: str | Decimal,
        duration_minutes: str | int,
        snapshot: FreqtradeSnapshot | None = None,
    ) -> RoundRecord:
        with self._lock:
            record = self.get_round(round_id)
            if record.state not in {RoundState.RUNNING, RoundState.WAITING_FOR_STRATEGY}:
                raise StateConflict("target and duration are frozen outside RUNNING")
            parsed_target = (
                _decimal_input(target_profit, "target_profit")
                if isinstance(target_profit, str)
                else _decimal_value(target_profit, "target_profit", positive=True)
            )
            seconds = _minutes_input(duration_minutes)
            updated = self.store.update_parameters(
                round_id,
                target_profit=parsed_target,
                duration_seconds=seconds * 60,
                now=self._now(),
            )
            self._event(
                updated,
                "parameters_updated",
                {"target_profit": _decimal_text(parsed_target), "duration_seconds": seconds * 60},
                self._now(),
            )
            return self.tick(round_id, snapshot=snapshot)

    def recover(self, round_id: str | None = None) -> RoundRecord:
        with self._lock:
            record = self.store.get_round(round_id) if round_id else self.store.current_round()
            if record is None:
                raise StateConflict("round does not exist")
            if record.terminal:
                return record
            now = self._now()
            try:
                self._pause_once(record, "recovery_pause", now)
                snapshot = self._snapshot(record)
            except ReconciliationError as exc:
                return self._recovery_hold(record, str(exc), now)
            if record.state in {RoundState.CLOSING, RoundState.RECONCILING}:
                return self._reconcile(record, snapshot, now)
            issues = list(self._release_issues(record))
            if self._risk_error:
                issues.append("risk_config_invalid")
            issues.extend(self._runtime_issues(snapshot, record, require_empty=False))
            if issues:
                if self._has_unprocessed(snapshot):
                    return self._begin_closing(
                        record,
                        RoundState.BLOCKED,
                        "release_integrity:" + ";".join(dict.fromkeys(issues)),
                        snapshot,
                        observed_reasons=issues,
                        now=now,
                    )
                return self._block(record, ";".join(dict.fromkeys(issues)))
            if record.state is RoundState.WAITING_FOR_STRATEGY:
                return self.tick(record.round_id, snapshot=snapshot, now=now)
            if record.started_at_utc is not None:
                record = self.store.update_round(
                    record.round_id,
                    timer_anchor_utc=_format_time(now),
                    updated_at=_format_time(now),
                )
            action = self.store.ensure_action(
                record.round_id, "recovery_start", RoundState.RUNNING, now=now
            )
            if action.status is ActionStatus.PENDING:
                try:
                    self._client_call("start")
                except Exception:
                    self.store.mark_action(
                        action.action_id,
                        ActionStatus.UNKNOWN,
                        increment_request=True,
                        now=self._now(),
                    )
                    return self._recovery_hold(record, "recovery_start_failed", now)
                self.store.mark_action(
                    action.action_id, ActionStatus.SENT, increment_request=True, now=self._now()
                )
            try:
                snapshot = self._snapshot(record)
            except ReconciliationError as exc:
                return self._recovery_hold(record, str(exc), now)
            return self.tick(record.round_id, snapshot=snapshot, now=now)

    def reauthorize(
        self,
        inputs: RoundInputs,
        *,
        release_id: str,
        approved_commit_sha: str,
    ) -> RoundRecord:
        with self._lock:
            current = self.store.current_round()
            if current is not None and not current.terminal:
                raise StateConflict("current round is not terminal")
            return self.create_round(
                inputs,
                release_id=release_id,
                approved_commit_sha=approved_commit_sha,
            )

    def record_research_unavailable(self, round_id: str, error_code: str) -> None:
        record = self.get_round(round_id)
        code = str(error_code).strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", code):
            code = "invalid_error_code"
        self.store.record_event(
            record.round_id,
            "codex_unavailable",
            {"error_code": code},
            created_at=self._now(),
        )

    def _now(self) -> datetime:
        current = self.clock()
        return current.astimezone(UTC) if current.tzinfo else current.replace(tzinfo=UTC)

    def _client_call(self, name: str) -> object:
        method = getattr(self.client, name, None)
        if not callable(method):
            raise RestError(f"Freqtrade action unavailable: {name}")
        previous_round_id = self._observation_round_id
        current = self.store.current_round()
        self._observation_round_id = current.round_id if current is not None else previous_round_id
        try:
            return method()
        finally:
            self._observation_round_id = previous_round_id

    def _check_input_against_runtime(self, inputs: RoundInputs) -> None:
        expected_currency = self.runtime_config.get("stake_currency")
        if not isinstance(expected_currency, str) or inputs.stake_currency != expected_currency:
            raise ValueError("stake_currency does not match runtime_config")
        wallet = self.runtime_config.get("dry_run_wallet")
        if (
            wallet is None
            or _decimal_value(wallet, "dry_run_wallet", positive=True) != inputs.capital
        ):
            raise ValueError("capital must exactly match runtime_config dry_run_wallet")

    def _release_issues(self, record: RoundRecord) -> tuple[str, ...]:
        if self.release_check is None:
            return ("release_check_unavailable",)
        try:
            result = self.release_check()
        except Exception:
            return ("release_check_unavailable",)
        if not isinstance(result, ReleaseVerification):
            return ("release_check_invalid",)
        issues = list(result.violations)
        if not result.allowed:
            issues.append("release_not_allowed")
        if result.release_id != record.release_id:
            issues.append("release_id_mismatch")
        if result.approved_commit_sha != record.approved_commit_sha:
            issues.append("approved_commit_sha_mismatch")
        return tuple(dict.fromkeys(str(issue) for issue in issues))

    def _snapshot(self, record: RoundRecord) -> FreqtradeSnapshot:
        previous_round_id = self._observation_round_id
        self._observation_round_id = record.round_id
        try:
            snapshot = self.client.snapshot()
        except ReconciliationError:
            raise
        except Exception as exc:
            raise ReconciliationError("api_unavailable") from exc
        finally:
            self._observation_round_id = previous_round_id
        if not isinstance(snapshot, FreqtradeSnapshot):
            raise ReconciliationError("snapshot_invalid")
        self.store.record_observation(
            record.round_id,
            "freqtrade_snapshot",
            status_code=200,
            summary={
                "health_present": bool(snapshot.health),
                "config_sha256": hashlib.sha256(
                    json.dumps(
                        snapshot.config, sort_keys=True, default=str, ensure_ascii=True
                    ).encode()
                ).hexdigest(),
                "open_trade_count": len(snapshot.open_trades),
                "closed_trade_count": len(snapshot.closed_trades),
                "open_order_count": len(snapshot.all_open_orders),
                "balance": _decimal_text(snapshot.balance),
            },
            observed_at=snapshot.observed_at,
        )
        return snapshot

    def _capture_rest_observation(
        self, endpoint: str, status_code: int | None, summary: object
    ) -> None:
        round_id = self._observation_round_id
        if round_id is None:
            current = self.store.current_round()
            round_id = current.round_id if current is not None else None
        if round_id is None:
            return
        self.store.record_observation(
            round_id,
            endpoint,
            status_code=status_code,
            summary=summary,
            observed_at=self._now(),
        )

    def _runtime_issues(
        self,
        snapshot: FreqtradeSnapshot,
        record: RoundRecord,
        *,
        require_empty: bool,
    ) -> list[str]:
        config = snapshot.config
        issues: list[str] = []
        if _as_bool(config.get("dry_run")) is not True:
            issues.append("dry_run_not_enabled")
        if config.get("stake_currency") != record.stake_currency:
            issues.append("stake_currency_mismatch")
        try:
            if _as_integer(config.get("max_open_trades"), "max_open_trades") != 1:
                issues.append("max_open_trades_must_be_one")
        except ReconciliationError:
            issues.append("max_open_trades_invalid")
        try:
            leverage = _decimal_value(config.get("leverage"), "leverage", positive=True)
            if leverage != Decimal("1"):
                issues.append("leverage_must_be_one")
        except ValueError:
            issues.append("leverage_invalid")
        try:
            configured_wallet = _decimal_value(
                config.get("dry_run_wallet"), "dry_run_wallet", positive=True
            )
            if configured_wallet != record.capital:
                issues.append("dry_run_wallet_mismatch")
        except ValueError:
            issues.append("dry_run_wallet_invalid")
        for key in (
            "strategy",
            "trading_mode",
            "margin_mode",
            "timeframe",
            "exchange",
            "leverage",
            "position_adjustment_enable",
        ):
            expected = self.runtime_config.get(key)
            if expected is not None and config.get(key) != expected:
                issues.append(f"{key}_mismatch")
        if self.runtime_config.get("dry_run") is not True:
            issues.append("runtime_dry_run_not_enabled")
        if self.runtime_config.get("max_open_trades") != 1:
            issues.append("runtime_max_open_trades_must_be_one")
        if require_empty and self._has_unprocessed(snapshot):
            issues.append("preexisting_trade_or_order")
        return list(dict.fromkeys(issues))

    def _confirm_start(
        self,
        record: RoundRecord,
        snapshot: FreqtradeSnapshot,
        now: datetime,
    ) -> RoundRecord:
        integrity = list(self._release_issues(record))
        if self._risk_error:
            integrity.append("risk_config_invalid")
        if integrity:
            return self._block(record, ";".join(dict.fromkeys(integrity)))
        issues = self._runtime_issues(snapshot, record, require_empty=False)
        if record.user_stop_requested:
            return self._finish(record, RoundState.STOPPED_USER, "user_stop")
        if not issues:
            action = self.store.get_action(record.round_id, "start")
            if action and action.status is not ActionStatus.COMPLETED:
                self.store.mark_action(action.action_id, ActionStatus.COMPLETED, now=now)
            return self.store.update_round(
                record.round_id,
                state=RoundState.RUNNING.value,
                startup_deadline_utc=None,
                last_observation_at=_format_time(snapshot.observed_at),
                last_balance=_decimal_text(snapshot.balance),
                updated_at=_format_time(now),
            )
        deadline = record.startup_deadline_utc
        if deadline is not None and now >= deadline:
            return self._block(record, "startup_confirmation_timeout:" + ";".join(issues))
        self._event(record, "startup_pending", {"reasons": issues}, now)
        return self.store.update_round(
            record.round_id,
            state=RoundState.STARTING.value,
            last_observation_at=_format_time(snapshot.observed_at),
            last_balance=_decimal_text(snapshot.balance),
            updated_at=_format_time(now),
        )

    def _hold_starting(self, record: RoundRecord, reason: str, now: datetime) -> RoundRecord:
        if record.startup_deadline_utc is not None and now >= record.startup_deadline_utc:
            return self._block(record, "startup_confirmation_timeout:" + reason)
        self._event(record, "startup_pending", {"reasons": [reason]}, now)
        return self.store.update_round(
            record.round_id,
            state=RoundState.STARTING.value,
            updated_at=_format_time(now),
        )

    def _max_trade_id(self, snapshot: FreqtradeSnapshot) -> int:
        values = [_trade_id(trade) for trade in (*snapshot.open_trades, *snapshot.closed_trades)]
        return max(values, default=0)

    def _round_trades(
        self,
        snapshot: FreqtradeSnapshot,
        record: RoundRecord,
    ) -> list[tuple[Mapping[str, object], bool]]:
        if record.start_trade_id_max is None:
            raise ReconciliationError("round_boundary_missing")
        found: dict[int, bool] = {}
        selected: list[tuple[Mapping[str, object], bool]] = []
        for collection, expected_open in (
            (snapshot.closed_trades, False),
            (snapshot.open_trades, True),
        ):
            for trade in collection:
                trade_id = _trade_id(trade)
                if trade_id <= record.start_trade_id_max:
                    continue
                is_open = _trade_is_open(trade)
                if is_open is not expected_open:
                    raise ReconciliationError("trade_state_conflict")
                fill_time = _fill_time(trade)
                if fill_time is None:
                    raise ReconciliationError("trade_fill_time_missing")
                if record.started_at_utc is not None and fill_time < record.started_at_utc:
                    raise ReconciliationError("trade_before_round_start")
                prior = found.get(trade_id)
                if prior is not None and prior is not is_open:
                    raise ReconciliationError("trade_id_state_conflict")
                if prior is not None:
                    raise ReconciliationError("trade_id_duplicate")
                found[trade_id] = is_open
                selected.append((trade, is_open))
        return selected

    @staticmethod
    def _has_unprocessed(snapshot: FreqtradeSnapshot) -> bool:
        return bool(snapshot.open_trades or snapshot.has_open_orders)

    def _metrics(
        self,
        snapshot: FreqtradeSnapshot,
        record: RoundRecord,
    ) -> tuple[Decimal, Decimal, Decimal]:
        if self.risk_config is None:
            raise ReconciliationError("risk_config_invalid")
        realized = Decimal("0")
        open_profit = Decimal("0")
        exit_cost = Decimal("0")
        for trade, is_open in self._round_trades(snapshot, record):
            value = _trade_profit(trade, closed=not is_open)
            if is_open:
                open_profit += value
                try:
                    amount = abs(_decimal_value(trade.get("amount"), "amount", positive=True))
                    current_rate = _decimal_value(
                        trade.get("current_rate"), "current_rate", positive=True
                    )
                except ValueError as exc:
                    raise ReconciliationError("open_trade_price_unavailable") from exc
                exposure = amount * current_rate
                exit_cost += exposure * self.risk_config.exit_cost_buffer_bps / Decimal("10000")
                exit_cost += _optional_cost(
                    trade,
                    "estimated_close_cost",
                    "estimated_exit_cost",
                    "exit_cost_buffer",
                )
            else:
                realized += value
        estimated = realized + open_profit - exit_cost
        if not self._has_unprocessed(snapshot) and record.starting_balance is not None:
            expected_balance = record.starting_balance + realized
            if abs(snapshot.balance - expected_balance) > Decimal("0.00000001"):
                raise ReconciliationError("balance_trade_conflict")
        return estimated, realized, max(Decimal("0"), -estimated)

    def _update_metrics(
        self,
        record: RoundRecord,
        snapshot: FreqtradeSnapshot,
        now: datetime,
    ) -> RoundRecord:
        estimated, realized, _loss = self._metrics(snapshot, record)
        return self.store.update_round(
            record.round_id,
            last_estimated_net=_decimal_text(estimated),
            last_realized_net=_decimal_text(realized),
            last_balance=_decimal_text(snapshot.balance),
            last_observation_at=_format_time(snapshot.observed_at),
            updated_at=_format_time(now),
        )

    def _advance_timer(
        self,
        record: RoundRecord,
        snapshot: FreqtradeSnapshot,
        now: datetime,
    ) -> RoundRecord:
        items = self._round_trades(snapshot, record)
        if record.started_at_utc is None and items:
            fill_times = [_fill_time(trade) for trade, _is_open in items]
            known_times = [value for value in fill_times if value is not None]
            if not known_times:
                raise ReconciliationError("trade_fill_time_missing")
            first_fill = min(known_times)
            elapsed = max(0, int((now - first_fill).total_seconds()))
            return self.store.update_round(
                record.round_id,
                started_at_utc=_format_time(first_fill),
                elapsed_seconds=elapsed,
                timer_anchor_utc=_format_time(now),
                updated_at=_format_time(now),
            )
        if record.started_at_utc is None:
            return record
        anchor = record.timer_anchor_utc or record.started_at_utc
        delta = max(0, int((now - anchor).total_seconds()))
        count_time = record.state in {RoundState.CLOSING, RoundState.RECONCILING}
        count_time = count_time or (snapshot.market_data_reliable and snapshot.qualifying_strategy)
        if not count_time:
            return self.store.update_round(
                record.round_id,
                timer_anchor_utc=_format_time(now),
                updated_at=_format_time(now),
            )
        if not delta:
            return record
        return self.store.update_round(
            record.round_id,
            elapsed_seconds=record.elapsed_seconds + delta,
            timer_anchor_utc=_format_time(now),
            updated_at=_format_time(now),
        )

    def _pause_once(self, record: RoundRecord, action_type: str, now: datetime) -> RoundRecord:
        action = self.store.ensure_action(
            record.round_id, action_type, RoundState.WAITING_FOR_STRATEGY, now=now
        )
        if action.status in {ActionStatus.PENDING, ActionStatus.UNKNOWN}:
            try:
                self._client_call("pause")
            except Exception:
                self.store.mark_action(
                    action.action_id,
                    ActionStatus.UNKNOWN,
                    increment_request=True,
                    now=self._now(),
                )
                self._event(record, "pause_request_failed", {}, self._now())
                return record
            self.store.mark_action(
                action.action_id,
                ActionStatus.COMPLETED,
                increment_request=True,
                now=self._now(),
            )
        return self.get_round(record.round_id)

    def _pause_for_waiting(self, record: RoundRecord, now: datetime) -> RoundRecord:
        return self._pause_once(record, "pause_waiting", now)

    @staticmethod
    def _reason_rank(reason: str | None) -> int:
        text = reason or ""
        if text.startswith("release_integrity") or text.startswith("reconciliation_error"):
            return 0
        if text == "loss_lock" or text.startswith("hard_loss"):
            return 1
        if text == "user_stop":
            return 2
        if text == "timeout":
            return 3
        if text == "target_estimate":
            return 4
        return 9

    def _choose_close_reason(self, current: str | None, candidate: str) -> str:
        return (
            candidate
            if self._reason_rank(candidate) < self._reason_rank(current)
            else (current or candidate)
        )

    def _begin_closing(
        self,
        record: RoundRecord,
        final_state: RoundState,
        reason: str,
        snapshot: FreqtradeSnapshot,
        *,
        observed_reasons: Sequence[str] = (),
        now: datetime,
    ) -> RoundRecord:
        if self._reason_rank(reason) != 0 and (
            record.loss_lock or final_state is RoundState.STOPPED_LOSS_LOCK
        ):
            reason = "loss_lock"
            final_state = RoundState.STOPPED_LOSS_LOCK
        existing = (
            self.store.get_action_by_id(record.pending_action_id)
            if record.pending_action_id
            else None
        )
        if record.state in {RoundState.CLOSING, RoundState.RECONCILING} and existing:
            chosen = self._choose_close_reason(record.stop_reason, reason)
            if chosen == "loss_lock" and not record.loss_lock:
                record = self.store.update_round(
                    record.round_id, loss_lock=1, updated_at=_format_time(now)
                )
            if chosen != record.stop_reason:
                record = self.store.update_round(
                    record.round_id,
                    stop_reason=chosen,
                    updated_at=_format_time(now),
                )
            record = self._issue_close(
                record, snapshot, now, keep_closing=record.state is RoundState.CLOSING
            )
            return (
                self._reconcile(record, snapshot, now)
                if not self._has_unprocessed(snapshot)
                else record
            )
        close_action = self.store.ensure_action(
            record.round_id,
            "close_round_" + uuid.uuid4().hex,
            RoundState.CLOSING,
            now=now,
        )
        record = self.store.update_round(
            record.round_id,
            state=RoundState.CLOSING.value,
            pending_action_id=close_action.action_id,
            stop_reason=reason,
            loss_lock=1 if final_state is RoundState.STOPPED_LOSS_LOCK else int(record.loss_lock),
            updated_at=_format_time(now),
        )
        self._event(
            record,
            "closing_requested",
            {"reason": reason, "observed_reasons": list(observed_reasons)},
            now,
        )
        record = self._pause_once(record, "pause_" + close_action.action_id, now)
        record = self._issue_close(record, snapshot, now, keep_closing=True)
        if not self._has_unprocessed(snapshot):
            return self._reconcile(record, snapshot, now)
        return record

    def _issue_close(
        self,
        record: RoundRecord,
        snapshot: FreqtradeSnapshot,
        now: datetime,
        *,
        keep_closing: bool,
    ) -> RoundRecord:
        action = (
            self.store.get_action_by_id(record.pending_action_id)
            if record.pending_action_id
            else None
        )
        if action is None:
            return self._block(record, "close_action_missing")
        if not self._has_unprocessed(snapshot):
            self.store.mark_action(action.action_id, ActionStatus.COMPLETED, now=now)
            return self.get_round(record.round_id)
        if now - action.created_at >= timedelta(seconds=CLOSING_RECONCILIATION_SECONDS):
            self._event(record, "reconciliation_timeout", {}, now)
            return self.store.update_round(
                record.round_id,
                state=RoundState.RECONCILING.value,
                updated_at=_format_time(now),
            )
        if not snapshot.open_trades:
            return self.store.update_round(
                record.round_id,
                state=RoundState.CLOSING.value if keep_closing else RoundState.RECONCILING.value,
                updated_at=_format_time(now),
            )
        if any(_open_exit_order(trade) for trade in snapshot.open_trades):
            return self.store.update_round(
                record.round_id,
                state=RoundState.CLOSING.value if keep_closing else RoundState.RECONCILING.value,
                updated_at=_format_time(now),
            )
        force_action = self.store.ensure_action(
            record.round_id,
            "forceexit_" + action.action_id,
            RoundState.CLOSING,
            now=now,
        )
        if force_action.status is not ActionStatus.COMPLETED:
            try:
                self._client_call("force_exit_all")
            except Exception:
                self.store.mark_action(
                    force_action.action_id,
                    ActionStatus.UNKNOWN,
                    increment_request=True,
                    now=self._now(),
                )
                self._event(record, "forceexit_request_uncertain", {}, self._now())
            else:
                self.store.mark_action(
                    force_action.action_id,
                    ActionStatus.SENT,
                    increment_request=True,
                    now=self._now(),
                )
        return self.store.update_round(
            record.round_id,
            state=RoundState.CLOSING.value if keep_closing else RoundState.RECONCILING.value,
            updated_at=_format_time(now),
        )

    def _reconcile(
        self,
        record: RoundRecord,
        snapshot: FreqtradeSnapshot | None,
        now: datetime,
    ) -> RoundRecord:
        if snapshot is None:
            try:
                snapshot = self._snapshot(record)
            except ReconciliationError as exc:
                self._event(record, "reconciliation_unavailable", {"reason": str(exc)}, now)
                return self.store.update_round(
                    record.round_id,
                    state=RoundState.RECONCILING.value,
                    updated_at=_format_time(now),
                )
        integrity = list(self._release_issues(record))
        if self._risk_error:
            integrity.append("risk_config_invalid")
        integrity.extend(self._runtime_issues(snapshot, record, require_empty=False))
        if integrity:
            reasons = list(dict.fromkeys(integrity))
            reason = "release_integrity:" + ";".join(reasons)
            record = self.store.update_round(
                record.round_id,
                state=RoundState.RECONCILING.value,
                stop_reason=self._choose_close_reason(record.stop_reason, reason),
                updated_at=_format_time(now),
            )
            self._event(record, "reconciliation_rejected", {"reasons": reasons}, now)
        if record.user_stop_requested:
            chosen = self._choose_close_reason(record.stop_reason, "user_stop")
            if chosen != record.stop_reason:
                record = self.store.update_round(
                    record.round_id, stop_reason=chosen, updated_at=_format_time(now)
                )
        try:
            record = self._update_metrics(record, snapshot, now)
            record = self._advance_timer(record, snapshot, now)
        except ReconciliationError as exc:
            self._event(record, "reconciliation_error", {"reason": str(exc)}, now)
            if self._has_unprocessed(snapshot):
                return self.store.update_round(
                    record.round_id,
                    state=RoundState.RECONCILING.value,
                    stop_reason=self._choose_close_reason(
                        record.stop_reason, "reconciliation_error:" + str(exc)
                    ),
                    updated_at=_format_time(now),
                )
            return self._finish(record, RoundState.BLOCKED, "reconciliation_error:" + str(exc))
        if record.last_estimated_net is not None and -record.last_estimated_net >= record.max_loss:
            record = self.store.update_round(
                record.round_id,
                loss_lock=1,
                stop_reason=self._choose_close_reason(record.stop_reason, "loss_lock"),
                updated_at=_format_time(now),
            )
        if self._has_unprocessed(snapshot):
            record = self.store.update_round(
                record.round_id,
                state=RoundState.RECONCILING.value,
                updated_at=_format_time(now),
            )
            record = self._issue_close(record, snapshot, now, keep_closing=False)
            if now - (
                self.store.get_action_by_id(record.pending_action_id).created_at
                if record.pending_action_id
                and self.store.get_action_by_id(record.pending_action_id)
                else now
            ) >= timedelta(seconds=CLOSING_RECONCILIATION_SECONDS):
                return self.store.update_round(
                    record.round_id,
                    state=RoundState.RECONCILING.value,
                    updated_at=_format_time(now),
                )
            return record
        if record.pending_action_id:
            self.store.mark_action(record.pending_action_id, ActionStatus.COMPLETED, now=now)
        if self._reason_rank(record.stop_reason) == 0:
            return self._finish(
                record, RoundState.BLOCKED, record.stop_reason or "integrity_failure"
            )
        if record.loss_lock or record.stop_reason == "loss_lock":
            return self._finish(record, RoundState.STOPPED_LOSS_LOCK, "loss_lock")
        if record.stop_reason == "user_stop":
            return self._finish(record, RoundState.STOPPED_USER, "user_stop")
        if record.stop_reason == "timeout":
            return self._finish(record, RoundState.COMPLETED_TIMEOUT, "timeout")
        if record.stop_reason == "target_estimate":
            if (
                record.last_realized_net is not None
                and record.last_realized_net >= record.target_profit
            ):
                return self._finish(record, RoundState.COMPLETED_TARGET, "target_settled")
            if record.elapsed_seconds >= record.duration_seconds:
                return self._finish(record, RoundState.COMPLETED_TIMEOUT, "timeout")
            resumed_state = (
                RoundState.WAITING_FOR_STRATEGY
                if snapshot is not None
                and (not snapshot.market_data_reliable or not snapshot.qualifying_strategy)
                else RoundState.RUNNING
            )
            record = self.store.update_round(
                record.round_id,
                state=resumed_state.value,
                pending_action_id=None,
                stop_reason=None,
                updated_at=_format_time(now),
            )
            self._event(record, "target_settlement_below_target", {}, now)
            return record
        return self._finish(record, RoundState.BLOCKED, "close_reason_missing")

    def _recovery_hold(self, record: RoundRecord, reason: str, now: datetime) -> RoundRecord:
        self._event(record, "recovery_blocked", {"reason": reason}, now)
        if record.state is RoundState.STARTING:
            return self._hold_starting(record, "recovery:" + reason, now)
        if record.state in {RoundState.CLOSING, RoundState.RECONCILING}:
            return self.store.update_round(
                record.round_id,
                state=RoundState.RECONCILING.value,
                updated_at=_format_time(now),
            )
        return self._block(record, "recovery:" + reason)

    def _event(
        self,
        record: RoundRecord,
        reason: str,
        details: Mapping[str, object],
        now: datetime,
    ) -> None:
        self.store.record_event(record.round_id, reason, details, created_at=now)

    def _block(self, record: RoundRecord, reason: str) -> RoundRecord:
        if record.terminal:
            return record
        updated = self.store.update_round(
            record.round_id,
            state=RoundState.BLOCKED.value,
            terminal=1,
            pending_action_id=None,
            stop_reason=reason,
            updated_at=_format_time(self._now()),
        )
        self._event(updated, "blocked", {"reason": reason}, self._now())
        return updated

    def _finish(self, record: RoundRecord, state: RoundState, reason: str) -> RoundRecord:
        if state is not RoundState.BLOCKED and (
            record.loss_lock or state is RoundState.STOPPED_LOSS_LOCK
        ):
            state = RoundState.STOPPED_LOSS_LOCK
            reason = "loss_lock"
        updated = self.store.update_round(
            record.round_id,
            state=state.value,
            terminal=1,
            pending_action_id=None,
            stop_reason=reason,
            loss_lock=1 if state is RoundState.STOPPED_LOSS_LOCK else int(record.loss_lock),
            updated_at=_format_time(self._now()),
        )
        self._event(
            updated, "round_finished", {"state": state.value, "reason": reason}, self._now()
        )
        return updated


RoundSupervisor = DryRunSupervisor


_WEB_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>1.0 单正式 Dry-run</title>
  <style>
    body { font: 16px system-ui, sans-serif; max-width: 52rem; margin: 2rem auto; padding: 0 1rem; }
    label { display: block; margin-top: .7rem; }
    input { width: 100%; max-width: 24rem; padding: .45rem; }
    button { margin: 1rem .5rem 0 0; padding: .55rem .8rem; }
    output { display: block; margin-top: 1rem; padding: .8rem; background: #f2f4f7; }
  </style>
</head>
<body>
  <h1>单正式 Dry-run 轮次</h1>
  <p>本页只显示监督状态；交易事实仍由 Freqtrade 提供。</p>
  <form id="round-form">
    <label>模拟本金 <input name="capital" inputmode="decimal" required></label>
    <label>目标净盈利 <input name="target_profit" inputmode="decimal" required></label>
    <label>有效时长（分钟） <input name="duration_minutes" inputmode="numeric" required></label>
    <label>最大净亏损 <input name="max_loss" inputmode="decimal" required></label>
    <label>发布 ID <input name="release_id" required></label>
    <label>批准 commit SHA <input name="approved_commit_sha" required></label>
    <button type="submit">创建轮次</button>
  </form>
  <button id="approve" type="button">批准并启动</button>
  <button id="stop" type="button">停止</button>
  <button id="reauthorize" type="button">重新授权</button>
  <output id="state" aria-live="polite">尚无轮次</output>
  <script>
    const form = document.querySelector("#round-form");
    const state = document.querySelector("#state");
    let roundId = null;
    async function refresh() {
      const response = await fetch("/api/state");
      const value = await response.json();
      roundId = value.round_id || roundId;
      state.textContent = value.state ? JSON.stringify(value) : "尚无轮次";
    }
    async function send(path, body) {
      const response = await fetch(path, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: body ? JSON.stringify(body) : undefined
      });
      const value = await response.json();
      state.textContent = JSON.stringify(value);
      roundId = value.round_id || roundId;
      return value;
    }
    function values() { return Object.fromEntries(new FormData(form).entries()); }
    form.addEventListener("submit", event => {
      event.preventDefault();
      send("/api/rounds", values()).then(refresh);
    });
    document.querySelector("#approve").addEventListener("click", () => {
      if (roundId) send("/api/rounds/" + roundId + "/approve").then(refresh);
    });
    document.querySelector("#stop").addEventListener("click", () => {
      if (roundId) send("/api/rounds/" + roundId + "/stop").then(refresh);
    });
    document.querySelector("#reauthorize").addEventListener("click", () => {
      send("/api/reauthorize", values()).then(refresh);
    });
    refresh();
    setInterval(refresh, 2000);
  </script>
</body>
</html>"""


def create_web_server(
    supervisor: DryRunSupervisor,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("supervision Web must bind to loopback")
    if not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("invalid Web port")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _send_json(self, status: int, value: Mapping[str, object]) -> None:
            body = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_page(self) -> None:
            body = _WEB_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict[str, object]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise ValueError("invalid request length") from exc
            if length < 0 or length > 32768:
                raise ValueError("request too large")
            raw = self.rfile.read(length)
            value = json.loads(raw.decode("utf-8")) if raw else {}
            if not isinstance(value, dict):
                raise ValueError("JSON object required")
            return value

        @staticmethod
        def _text(body: Mapping[str, object], key: str) -> str:
            value = body.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{key} is required")
            return value

        def _inputs(self, body: Mapping[str, object]) -> tuple[RoundInputs, str, str]:
            inputs = RoundInputs.from_strings(
                capital=self._text(body, "capital"),
                target_profit=self._text(body, "target_profit"),
                duration_minutes=self._text(body, "duration_minutes"),
                max_loss=self._text(body, "max_loss"),
                stake_currency=str(supervisor.runtime_config.get("stake_currency", "")),
                dry_run_wallet=supervisor.runtime_config.get("dry_run_wallet"),
            )
            return inputs, self._text(body, "release_id"), self._text(body, "approved_commit_sha")

        def do_GET(self) -> None:
            path = urllib.parse.urlsplit(self.path).path
            if path == "/":
                self._send_page()
                return
            if path == "/api/state":
                self._send_json(200, supervisor.state_payload())
                return
            self._send_json(404, {"error": "not_found"})

        def do_POST(self) -> None:
            path = urllib.parse.urlsplit(self.path).path
            try:
                body = self._body()
                if path == "/api/rounds":
                    inputs, release_id, commit_sha = self._inputs(body)
                    result = supervisor.create_round(
                        inputs,
                        release_id=release_id,
                        approved_commit_sha=commit_sha,
                    )
                    self._send_json(201, result.as_dict())
                    return
                if path == "/api/reauthorize":
                    inputs, release_id, commit_sha = self._inputs(body)
                    result = supervisor.reauthorize(
                        inputs,
                        release_id=release_id,
                        approved_commit_sha=commit_sha,
                    )
                    self._send_json(201, result.as_dict())
                    return
                if path == "/api/stop":
                    self._send_json(200, supervisor.request_stop().as_dict())
                    return
                prefix = "/api/rounds/"
                if path.startswith(prefix):
                    suffix = path[len(prefix) :]
                    round_id, _, action = suffix.rpartition("/")
                    if not round_id or action not in {"approve", "stop"}:
                        raise ValueError("unknown round action")
                    result = (
                        supervisor.approve_and_start(round_id)
                        if action == "approve"
                        else supervisor.request_stop(round_id)
                    )
                    self._send_json(200, result.as_dict())
                    return
                self._send_json(404, {"error": "not_found"})
            except StateConflict as exc:
                self._send_json(409, {"error": "state_conflict", "message": str(exc)})
            except (TypeError, ValueError, json.JSONDecodeError):
                self._send_json(400, {"error": "invalid_request"})
            except Exception:
                self._send_json(503, {"error": "supervision_unavailable"})

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.allow_reuse_address = True
    server.supervisor = supervisor  # type: ignore[attr-defined]
    return server
