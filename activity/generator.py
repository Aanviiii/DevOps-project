"""Patron activity generator: keeps a Shelfwise library busy, like a real day at the desk.

Every few seconds it does one thing a librarian or patron would do: browse or search
the catalogue, lend a book, return or renew one, place a hold when a book is out, or
settle a member's fines. Requests go through the public API, so every lending rule
applies and the metrics and dashboards show realistic traffic, refusals included.

Standard library only, so the image stays tiny.

Environment:
  SHELFWISE_API_URL   base URL of the backend (default http://shelfwise-backend:8000)
  ACTIONS_PER_MINUTE  pace of activity (default 30)
"""

import json
import logging
import os
import random
import signal
import time
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("SHELFWISE_API_URL", "http://shelfwise-backend:8000").rstrip("/")
PACE = max(1, int(os.environ.get("ACTIONS_PER_MINUTE", "30")))
SEARCH_TERMS = ["code", "history", "the", "data", "science", "kalam", "dune", "habits"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("activity")
rng = random.Random()  # noqa: S311 - picks plausible activity, not secrets
running = True


def stop(*_):
    global running
    running = False


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)


def call(method: str, path: str, body: dict | None = None, **params):
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(  # noqa: S310 - URL comes from our own config
        url, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as refused:
        payload = refused.read()
        try:
            return refused.code, json.loads(payload)
        except ValueError:
            return refused.code, None


def desk_request(path: str, book_id: int, member_id: int):
    return call("POST", path, {"book_id": book_id, "member_id": member_id})


def browse():
    status, _ = call("GET", "/api/books", q=rng.choice(SEARCH_TERMS))
    return f"search catalogue -> {status}"


def lend():
    _, books = call("GET", "/api/books")
    _, members = call("GET", "/api/members", active="true")
    if not books or not members:
        return "lend skipped (empty library)"
    book, member = rng.choice(books), rng.choice(members)
    status, body = desk_request("/api/loans", book["id"], member["id"])
    if status == 409 and body and body.get("code") == "NOT_AVAILABLE" and rng.random() < 0.5:
        status, body = desk_request("/api/holds", book["id"], member["id"])
        return f"hold on '{book['title']}' for {member['full_name']} -> {status}"
    detail = body.get("code") if status == 409 and body else ""
    return f"lend '{book['title']}' to {member['full_name']} -> {status} {detail}".rstrip()


def give_back():
    _, loans = call("GET", "/api/loans", state="active")
    if not loans:
        return "return skipped (nothing on loan)"
    loan = rng.choice(loans)
    action = "renew" if rng.random() < 0.25 else "return"
    status, body = call("POST", f"/api/loans/{loan['id']}/{action}")
    detail = body.get("code") if status == 409 and body else ""
    return f"{action} '{loan['book_title']}' -> {status} {detail}".rstrip()


def collect_hold():
    _, ready = call("GET", "/api/holds", status="READY")
    if not ready:
        return browse()
    hold = rng.choice(ready)
    status, _ = desk_request("/api/loans", hold["book_id"], hold["member_id"])
    return f"{hold['member_name']} collects '{hold['book_title']}' -> {status}"


def settle():
    _, members = call("GET", "/api/members")
    if not members:
        return "settle skipped"
    member = rng.choice(members)
    status, body = call("POST", f"/api/members/{member['id']}/settle-fines")
    return f"settle fines for {member['full_name']} -> {status} (₹{(body or {}).get('settled', 0)})"


# Weighted like a real desk: lots of browsing, lending and returning, a few payments.
ACTIONS = [(browse, 30), (lend, 30), (give_back, 25), (collect_hold, 10), (settle, 5)]


def main():
    log.info("generating activity against %s at %d actions/minute", API, PACE)
    functions, weights = zip(*ACTIONS, strict=True)
    while running:
        action = rng.choices(functions, weights)[0]
        try:
            log.info(action())
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            log.warning("API unreachable: %s", error)
        # Jitter so several generators never march in lockstep.
        time.sleep(rng.uniform(0.5, 1.5) * 60 / PACE)
    log.info("stopped")


if __name__ == "__main__":
    main()
