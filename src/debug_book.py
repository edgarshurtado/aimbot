"""Throwaway diagnostic entrypoint for tracing a single booking attempt.

Not part of the application, and not intended for master.

It drives the real AimHarderClient (so every HTTP request is genuine production
code) but skips the scheduler, the repositories' write paths and Telegram, so
nothing is mutated. Read-only by default; `--commit` sends the real POST.

    PYTHONPATH=src python src/debug_book.py --day 2026-08-13 --time 19:00 --class WOD
    PYTHONPATH=src python src/debug_book.py --day 2026-08-13 --time 19:00 --class WOD --commit
"""

import argparse
import json
import os
import sys
from datetime import datetime
from itertools import count

import requests
from dotenv import load_dotenv

load_dotenv()

from constants import AUTH_COOKIE_NAME, LOGIN_ENDPOINT  # noqa: E402
from domain.exceptions import AuthenticationFailed, BookingFailed  # noqa: E402
from domain.models import User  # noqa: E402
from infrastructure.aimharder.client_factory import AimHarderClientFactory  # noqa: E402
from infrastructure.aimharder.gym_config import IAimHarderGym  # noqa: E402
from infrastructure.persistence.json_repository import JsonRepository  # noqa: E402

STDOUT_BODY_LIMIT = 300

REDACTED_KEYS = {"pw", "password", "pass", "token", "apikey"}
MASKED_KEYS = {"mail", "email"}

# Authentication is proven by the session cookie, nothing else. The platform serves
# unauthenticated sessions ordinary-looking 200s and answers the class listing with
# real data, so no amount of reading response bodies can establish that login worked.


# ── trace output ─────────────────────────────────────────────────────────────


class Trace:
    """Scannable trace on stdout, complete bodies in a file."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._fh = open(path, "w", encoding="utf-8")

    def step(self, tag: str, message: str) -> None:
        line = f"[{tag}]".ljust(10) + message
        print(line, flush=True)
        self._write(line)

    def detail(self, message: str) -> None:
        """File only — the stuff that would bury stdout."""
        self._write(message)

    def blank(self) -> None:
        print("", flush=True)
        self._write("")

    def _write(self, text: str) -> None:
        self._fh.write(text + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


def _mask_email(value: str) -> str:
    local, _, domain = str(value).partition("@")
    return f"{local[:3]}***@{domain}" if domain else f"{local[:3]}***"


def _redact(payload) -> dict:
    if not isinstance(payload, dict):
        return payload
    safe = {}
    for key, value in payload.items():
        lowered = str(key).lower()
        if lowered in REDACTED_KEYS:
            safe[key] = "***"
        elif lowered in MASKED_KEYS:
            safe[key] = _mask_email(value)
        else:
            safe[key] = value
    return safe


# ── HTTP tracer ──────────────────────────────────────────────────────────────


class HttpTracer:
    """Wraps requests.Session.request so no call can slip past unlogged.

    Session.get/post both funnel through Session.request, so this also captures
    the login that happens inside AimHarderClient.__init__.
    """

    def __init__(self, trace: Trace) -> None:
        self._trace = trace
        self._counter = count(1)
        self._original = None
        self.responses: list = []

    def install(self) -> None:
        self._original = requests.Session.request
        original = self._original
        tracer = self

        def traced(session, method, url, **kwargs):
            number = next(tracer._counter)
            tracer._log_request(number, method, url, kwargs)
            response = original(session, method, url, **kwargs)
            tracer._log_response(number, response)
            tracer.responses.append(response)
            return response

        requests.Session.request = traced

    def uninstall(self) -> None:
        if self._original is not None:
            requests.Session.request = self._original

    def find_response(self, predicate):
        """Most recent response whose URL satisfies predicate."""
        for response in reversed(self.responses):
            if predicate(response.request.url or ""):
                return response
        return None

    def _log_request(self, number: int, method: str, url: str, kwargs: dict) -> None:
        params = _redact(kwargs.get("params") or {})
        data = _redact(kwargs.get("data") or {})
        summary = f"--> #{number} {method} {url}"
        if params:
            summary += f" params={params}"
        if data:
            summary += f" data={data}"
        self._trace.step("http", summary)

    def _log_response(self, number: int, response) -> None:
        elapsed = response.elapsed.total_seconds() * 1000
        cookie_names = sorted({cookie.name for cookie in response.cookies})
        content_type = response.headers.get("Content-Type", "?").split(";")[0]
        line = (
            f"<-- #{number} {response.status_code} {content_type}"
            f" {len(response.content)}B {elapsed:.0f}ms"
        )
        if cookie_names:
            line += f" set-cookie={cookie_names}"
        if response.history:
            line += f" redirects={[r.status_code for r in response.history]} -> {response.url}"
        self._trace.step("http", line)

        body = response.text
        preview = body[:STDOUT_BODY_LIMIT].replace("\n", " ")
        if len(body) > STDOUT_BODY_LIMIT:
            preview += f"… (+{len(body) - STDOUT_BODY_LIMIT}B, full body in log file)"
        self._trace.step("http", f"    body: {preview}")
        self._trace.detail(f"--- full body of #{number} ({response.request.url}) ---")
        self._trace.detail(body)
        self._trace.detail(f"--- end body of #{number} ---")


# ── gym config ───────────────────────────────────────────────────────────────


class CliGymConfig(IAimHarderGym):
    def __init__(self, box_id: int, box_name: str, days_in_advance: int) -> None:
        self._box_id = box_id
        self._box_name = box_name
        self._days_in_advance = days_in_advance

    @property
    def box_id(self) -> int:
        return self._box_id

    @property
    def box_name(self) -> str:
        return self._box_name

    @property
    def days_in_advance(self) -> int:
        return self._days_in_advance


def resolve_gym_config(args) -> CliGymConfig:
    """Env vars, with CLI flags taking precedence. Reports everything missing at once."""
    settings = {
        "MONKEY_BOX_ID": (args.box_id, int),
        "MONKEY_BOX_NAME": (args.box_name, str),
        "MONKEY_BOX_DAYS_IN_ADVANCE": (args.days_in_advance, int),
    }
    resolved, missing = {}, []
    for env_name, (cli_value, cast) in settings.items():
        if cli_value is not None:
            resolved[env_name] = cast(cli_value)
        elif env_name in os.environ:
            resolved[env_name] = cast(os.environ[env_name])
        else:
            missing.append(env_name)

    if missing:
        raise SystemExit(
            "Missing gym configuration: "
            + ", ".join(missing)
            + "\nSet them in the environment (as the deployed container does) or pass"
            " --box-id / --box-name / --days-in-advance."
        )

    return CliGymConfig(
        box_id=resolved["MONKEY_BOX_ID"],
        box_name=resolved["MONKEY_BOX_NAME"],
        days_in_advance=resolved["MONKEY_BOX_DAYS_IN_ADVANCE"],
    )


def resolve_user(repo: JsonRepository, user_id: int | None) -> User:
    if user_id is not None:
        user = repo.get_user(user_id)
        if user is None:
            raise SystemExit(f"User {user_id} not found in schedule.json")
        return user

    users = repo.get_all_users()
    if len(users) != 1:
        raise SystemExit(
            f"schedule.json holds {len(users)} users — pass --user to pick one:"
            f" {[u.id for u in users]}"
        )
    return users[0]


# ── stages ───────────────────────────────────────────────────────────────────


def stage_env(trace: Trace, gym: CliGymConfig, class_start: datetime) -> None:
    now = datetime.now()
    trigger = gym.booking_trigger_time(class_start)
    delta = trigger - now
    when = "in the future" if delta.total_seconds() > 0 else "in the PAST"

    trace.step(
        "env",
        f"box_id={gym.box_id} box_name={gym.box_name!r} days_in_advance={gym.days_in_advance}",
    )
    trace.step(
        "env",
        f"local now={now:%Y-%m-%d %H:%M:%S} tz={now.astimezone().tzname()} utc_offset={now.astimezone().utcoffset()}",
    )
    trace.step("env", f"target class_start={class_start:%Y-%m-%d %H:%M}")
    trace.step(
        "env",
        f"trigger time would be {trigger:%Y-%m-%d %H:%M} ({when}, {abs(delta)} away)",
    )
    if delta.total_seconds() > 0:
        trace.step(
            "env",
            "NOTE: booking window is (per our estimate) not open yet — a --commit run here is safe and captures the 'too early' response",
        )


def stage_user(trace: Trace, user: User) -> None:
    trace.step(
        "user",
        f"id={user.id} email={_mask_email(user.email)} goals={len(user.booking_goals)}",
    )
    for goal in user.booking_goals:
        trace.step(
            "user", f"  goal: {goal.class_start:%Y-%m-%d %H:%M} {goal.class_name!r}"
        )


def stage_login(trace: Trace, tracer: HttpTracer, client) -> None:
    response = tracer.find_response(lambda url: url.startswith(LOGIN_ENDPOINT))
    if response is None:
        trace.step("login", "no login request captured — unexpected")
        return

    cookies = client._session.cookies  # private, but this is a debug script
    trace.step("login", f"POST {LOGIN_ENDPOINT} -> {response.status_code}")
    trace.step("login", f"final url={response.url}")
    trace.step("login", f"session cookies={sorted(cookies.keys())}")

    token = cookies.get(AUTH_COOKIE_NAME)
    if token:
        trace.step(
            "login",
            f"authenticated: CONFIRMED — {AUTH_COOKIE_NAME} issued ({len(token)} chars),"
            " scoped to reach the gym subdomain",
        )
    else:
        trace.step(
            "login",
            f"authenticated: NO — {AUTH_COOKIE_NAME} missing. AimHarderClient raises in"
            " this case, so reaching here without it means the client itself is broken.",
        )
    trace.step(
        "login",
        "note: the cookie proves login succeeded, not that the session is still live."
        " Only the [book] response can show that — the class listing below answers"
        " unauthenticated callers with real data too.",
    )


def stage_classes(trace: Trace, tracer: HttpTracer, classes: list) -> list[dict]:
    response = tracer.find_response(lambda url: "/api/bookings" in url)
    raw_entries = []
    if response is not None:
        try:
            raw_entries = response.json().get("bookings") or []
        except ValueError:
            trace.step("classes", "response was not JSON — see full body in log file")
            return []

    trace.step(
        "classes", f"{len(raw_entries)} raw bookings -> {len(classes)} GymClass objects"
    )
    if not raw_entries:
        trace.step(
            "classes",
            "EMPTY — wrong box/day params, an unauthenticated session, or the box is closed",
        )
        return raw_entries

    header = f"  {'raw id':<10} | {'className':<18} | {'timeid':<9} | {'ocup/limit':<10} | derived start"
    trace.step("classes", header)
    for raw, gym_class in zip(raw_entries, classes):
        occupancy = f"{raw.get('ocupation')}/{raw.get('limit')}"
        trace.step(
            "classes",
            f"  {str(raw.get('id')):<10} | {str(raw.get('className')):<18} |"
            f" {str(raw.get('timeid')):<9} | {occupancy:<10} |"
            f" {gym_class.class_start:%Y-%m-%d %H:%M}",
        )
    for raw in raw_entries:
        trace.detail(f"raw entry: {json.dumps(raw, ensure_ascii=False)}")
    return raw_entries


def stage_idmap(trace: Trace, classes: list, client) -> None:
    seen: dict = {}
    duplicates = []
    for gym_class in classes:
        key = (gym_class.name, gym_class.class_start)
        if key in seen:
            duplicates.append(key)
        seen[key] = gym_class

    trace.step("idmap", f"{len(client._id_map)} entries for {len(classes)} classes")
    if duplicates:
        for name, start in duplicates:
            trace.step(
                "idmap",
                f"COLLISION on ({name!r}, {start:%H:%M}) — client.py keys _id_map on"
                " (name, start), so the later class silently overwrote the earlier one."
                " The booked id may not be the class you meant.",
            )
    else:
        trace.step("idmap", "no (name, start) collisions")


def stage_match(trace: Trace, classes: list, class_start: datetime, class_name: str):
    trace.step(
        "match",
        f"want name containing {class_name!r} starting exactly {class_start:%Y-%m-%d %H:%M}",
    )
    matched = None
    for gym_class in classes:
        time_ok = gym_class.class_start == class_start
        name_ok = class_name in gym_class.name
        hit = time_ok and name_ok
        reasons = []
        if not time_ok:
            reasons.append("start differs")
        if not name_ok:
            reasons.append("name has no substring")
        trace.step(
            "match",
            f"  {'HIT ' if hit else '    '}{gym_class.name!r:<20}"
            f" {gym_class.class_start:%H:%M} spots={gym_class.spots_available}/{gym_class.max_spots}"
            + (f"   ({', '.join(reasons)})" if reasons else ""),
        )
        if hit and matched is None:
            matched = gym_class

    if matched is None:
        trace.step(
            "match",
            "VERDICT: no match — ExecuteBookingUseCase would raise BookingFailed here",
        )
        return None

    trace.step(
        "match", f"VERDICT: matched {matched.name!r} at {matched.class_start:%H:%M}"
    )
    if matched.name != class_name:
        trace.step(
            "match",
            f"WARNING: substring match — goal {class_name!r} matched class {matched.name!r}."
            " execute_booking.py uses `booking_goal.class_name in c.name`.",
        )
    if matched.spots_available <= 0:
        trace.step(
            "match",
            "WARNING: class is FULL — aimharder may accept the POST without booking",
        )
    return matched


def stage_book(
    trace: Trace, tracer: HttpTracer, client, matched, commit: bool, class_id: str
):
    if not commit:
        day = matched.class_start.strftime("%Y%m%d")
        trace.step("book", "SKIPPED (read-only). Would POST:")
        trace.step(
            "book", f"  data={{'id': {class_id!r}, 'day': {day!r}, 'insist': 0}}"
        )
        trace.step("book", "  re-run with --commit to send it")
        return None

    trace.step("book", f"POSTing for class id={class_id}")
    raised = None
    try:
        client.book_class(matched)
    except (BookingFailed, AuthenticationFailed) as error:
        raised = error

    response = tracer.find_response(lambda url: url.rstrip("/").endswith("/api/book"))
    if response is None:
        trace.step("book", "no /api/book request captured — unexpected")
        return None

    trace.step("book", f"status={response.status_code}")
    try:
        data = response.json()
    except ValueError:
        trace.step(
            "book", "response was NOT JSON — client.book_class() would raise on .json()"
        )
        return None

    trace.step("book", f"body={json.dumps(data, ensure_ascii=False)}")
    trace.step("book", f"bookState={data.get('bookState', '<absent>')!r}")
    trace.step(
        "book",
        f"errorMssg={'present' if 'errorMssg' in data else 'absent'}"
        f" errorMssgLang={'present' if 'errorMssgLang' in data else 'absent'}",
    )

    trace.step(
        "book", f"logout sentinel={'PRESENT' if data.get('logout') else 'absent'}"
    )

    if isinstance(raised, AuthenticationFailed):
        trace.step(
            "book",
            f"VERDICT: session was not authenticated — {raised}. Nothing was booked."
            " This is the failure that used to be reported as success.",
        )
    elif raised is not None:
        trace.step("book", f"VERDICT: client raised {type(raised).__name__}({raised})")
    elif "errorMssg" not in data and "errorMssgLang" not in data:
        trace.step(
            "book",
            "VERDICT: client treats this as SUCCESS — note it infers success from the"
            " ABSENCE of error keys, not from bookState. Check [verify] below for what"
            " aimharder actually did.",
        )
    else:
        trace.step("book", "VERDICT: client returned without raising, unexpectedly")
    return response


def stage_verify(
    trace: Trace,
    tracer: HttpTracer,
    client,
    class_start: datetime,
    class_id: str,
    before: list[dict],
) -> None:
    trace.step(
        "verify",
        "re-fetching the day's classes to see what aimharder actually recorded",
    )
    client.get_classes(class_start)

    trace.step("verify", "comparing the target class entry before/after")
    after_entries = _bookings_entries(trace, tracer)
    before_entry = next((e for e in before if str(e.get("id")) == str(class_id)), None)
    after_entry = next(
        (e for e in after_entries if str(e.get("id")) == str(class_id)), None
    )

    if before_entry is None or after_entry is None:
        trace.step(
            "verify",
            "could not locate the class in one of the snapshots — see log file",
        )
        return

    changed = [
        (key, before_entry.get(key), after_entry.get(key))
        for key in sorted(set(before_entry) | set(after_entry))
        if before_entry.get(key) != after_entry.get(key)
    ]
    if not changed:
        trace.step(
            "verify",
            "NOTHING CHANGED — aimharder did not record a booking. The 'success' was fictional.",
        )
        return

    trace.step("verify", "fields that changed:")
    for key, old, new in changed:
        trace.step("verify", f"  {key}: {old!r} -> {new!r}")
    trace.step(
        "verify",
        "if ocupation incremented or a booking id appeared, the booking is real",
    )


def _bookings_entries(trace: Trace, tracer: HttpTracer) -> list[dict]:
    response = tracer.find_response(lambda url: "/api/bookings" in url)
    if response is None:
        return []
    try:
        return response.json().get("bookings") or []
    except ValueError:
        trace.step("verify", "re-fetch was not JSON")
        return []


# ── entrypoint ───────────────────────────────────────────────────────────────


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Trace a single aimharder booking attempt."
    )
    parser.add_argument("--day", required=True, help="class day, YYYY-MM-DD")
    parser.add_argument("--time", required=True, help="class start, HH:MM")
    parser.add_argument(
        "--class", dest="class_name", required=True, help="class name, e.g. WOD"
    )
    parser.add_argument(
        "--user",
        type=int,
        default=None,
        help="telegram user id (default: the only user in schedule.json)",
    )
    parser.add_argument(
        "--commit", action="store_true", help="actually send POST /api/book"
    )
    parser.add_argument("--box-id", type=int, default=None)
    parser.add_argument("--box-name", default=None)
    parser.add_argument("--days-in-advance", type=int, default=None)
    parser.add_argument("--log-file", default=None)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    log_path = args.log_file or f"/tmp/aimbot-debug-{datetime.now():%Y%m%d-%H%M%S}.log"
    trace = Trace(log_path)
    tracer = HttpTracer(trace)
    tracer.install()

    try:
        class_start = datetime.strptime(f"{args.day} {args.time}", "%Y-%m-%d %H:%M")
        gym = resolve_gym_config(args)

        stage_env(trace, gym, class_start)
        trace.blank()

        user = resolve_user(JsonRepository(), args.user)
        stage_user(trace, user)
        trace.blank()

        client = AimHarderClientFactory(gym=gym).create(user)
        stage_login(trace, tracer, client)
        trace.blank()

        classes = client.get_classes(class_start)
        raw_before = stage_classes(trace, tracer, classes)
        trace.blank()

        stage_idmap(trace, classes, client)
        trace.blank()

        matched = stage_match(trace, classes, class_start, args.class_name)
        trace.blank()
        if matched is None:
            return 1

        class_id = client._id_map[(matched.name, matched.class_start)]
        stage_book(trace, tracer, client, matched, args.commit, class_id)
        trace.blank()

        if args.commit:
            stage_verify(trace, tracer, client, class_start, class_id, raw_before)
        return 0
    except SystemExit:
        raise
    except Exception as error:  # noqa: BLE001 - diagnostic script, report everything
        trace.step("fatal", f"{type(error).__name__}: {error}")
        import traceback

        trace.detail(traceback.format_exc())
        traceback.print_exc()
        return 2
    finally:
        tracer.uninstall()
        print(f"\nfull trace: {log_path}", flush=True)
        trace.close()


if __name__ == "__main__":
    sys.exit(main())
