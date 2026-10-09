"""Escalation down `watch.escalation` and acknowledgements (06 §3).

- `start_chain` sends to step `start`, then onwards while a step fails delivery (`ALERT_FAILED` → next) or is
  skipped (its phone is the swapped line and no backup exists). A step with `requires_ack` that was delivered
  parks the chain in `AlertsState` (`esc#…`) with `sent_at`; a step without it ends the chain.
- `tick` (every poll, and the local scheduler's minute tick) moves a parked chain on once `ESCALATE_NEXT`
  (15 min) has passed without an acknowledgement — re-resolving the grant first, auditing the release.
- `handle_reply` takes an SMS reply ("OK" or "CANCEL", from the SNS inbound topic or the local gateway). The
  replying number is hashed to a line id at once; the number itself goes no further than a SIM-swap check.
  A reply from a line within `ACK_DISTRUST` (24 h) of its own SIM swap is **ignored**, audited
  `ACK_IGNORED_SWAPPED_LINE`, the chain continues, and the watcher's next message says so
  (`templates.ACK_IGNORED_NOTE`). A carrier error on that check counts as "swapped" (fail closed), except
  `NOT_BOUND` (the number is not this carrier's), which cannot be caused by a swap here.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from camara_client import CarrierError, LineRef
from tower_audit import Trigger
from tower_consent import get_line, get_watch, list_watches_for_line
from tower_consent import tables as T
from tower_policy import Facts, ReasonCode

from alerts import state as S
from alerts.context import AlertsService, audit
from alerts.evaluate import watch_consent
from alerts.send import Recipient, line_swapped_state, phone_for_user, recipient, send_one
from alerts.templates import ACK_IGNORED_NOTE, message_ref, render
from alerts.windows import swap_distrusted

log = logging.getLogger("alerts.escalation")

ACK_WORDS = frozenset({"OK", "CANCEL"})


def chain_recipient(svc: AlertsService, user_id: str, line_id: str, swapped: bool) -> Recipient | None:
    """A chain member's phone; if it *is* the swapped line, their backup phone instead, else skip them."""
    line = get_line(svc.store, line_id)
    default = line if line is not None and line.owner_user_id == user_id else None
    r = recipient(svc, user_id, "chain", phone_for_user(svc, user_id, default_line=default))
    if r is None or not (swapped and r.phone_line_id == line_id):
        return r
    item = svc.store.get(T.USERS, {"user_id": user_id}) or {}
    enc = item.get("backup_phone_enc")
    backup = recipient(svc, user_id, "backup", svc.cipher.decrypt(enc) if isinstance(enc, str) else None)
    if backup is not None and backup.phone_line_id != line_id:
        return backup
    log.info("chain step skipped: %s's phone is the swapped line", user_id)
    svc.count("swapped_line_skipped")
    return None


async def start_chain(
    svc: AlertsService,
    *,
    line_id: str,
    watcher_user_id: str,
    steps: tuple[tuple[str, bool], ...],
    codes: tuple[ReasonCode, ...],
    facts: Facts,
    alias: str | None,
    tz: str,
    now: datetime,
    trigger: Trigger,
    start: int,
    swapped: bool,
) -> list[str]:
    """Send from step `start`; returns the labels texted. Parks or clears the escalation state."""
    chain = steps or ((watcher_user_id, False),)
    body = render(codes, facts, alias=alias, tz=tz, now=now)
    ref = message_ref(codes)
    labels: list[str] = []
    for i in range(start, len(chain)):
        user_id, requires_ack = chain[i]
        r = chain_recipient(svc, user_id, line_id, swapped)
        if r is None:
            continue
        if not await send_one(svc, r, body, line_id=line_id, now=now, trigger=trigger, ref=ref):
            continue
        labels.append(r.label)
        if requires_ack:
            S.save_escalation(
                svc.store,
                S.Escalation(
                    line_id=line_id,
                    watcher_user_id=watcher_user_id,
                    codes=list(codes),
                    facts=facts,
                    alias=alias,
                    tz=tz,
                    step=i,
                    sent_at=now,
                ),
            )
            S.remember_ack_route(svc.store, r.phone_line_id, line_id, watcher_user_id, now)
            return labels
        break
    S.clear_escalation(svc.store, line_id, watcher_user_id)
    return labels


async def tick(svc: AlertsService, now: datetime) -> list[str]:
    """Move every parked chain whose ack window has passed. Returns the labels texted."""
    texted: list[str] = []
    for esc in S.list_escalations(svc.store):
        if esc.acked:
            S.clear_escalation(svc.store, esc.line_id, esc.watcher_user_id)
            continue
        if now - esc.sent_at < svc.thresholds.ESCALATE_NEXT:
            continue
        watch = get_watch(svc.store, esc.line_id, esc.watcher_user_id)
        if watch is None or not watch.enabled:
            S.clear_escalation(svc.store, esc.line_id, esc.watcher_user_id)
            continue
        consent = watch_consent(svc, esc.line_id, esc.watcher_user_id)
        if consent.refused:
            audit(
                svc,
                esc.line_id,
                now,
                trigger="poll",
                outcome="suppressed",
                codes=[ReasonCode.SUPPRESSED_REVOKED],
            )
            S.clear_escalation(svc.store, esc.line_id, esc.watcher_user_id)
            continue
        codes = tuple(esc.codes)
        ref = message_ref(codes)
        audit(svc, esc.line_id, now, trigger="poll", outcome="changed", codes=codes, message_ref=ref)
        swapped = line_swapped_state(svc, codes, esc.facts, now)
        steps = tuple((s.user_id, s.requires_ack) for s in watch.escalation)
        if esc.ack_ignored and not esc.note_sent:
            w = chain_recipient(svc, esc.watcher_user_id, esc.line_id, swapped)
            body = render(codes, esc.facts, alias=esc.alias, tz=esc.tz, now=now) + " " + ACK_IGNORED_NOTE
            if w is not None and await send_one(
                svc, w, body, line_id=esc.line_id, now=now, trigger="poll", ref=ref
            ):
                texted.append(w.label)
        log.info("escalate line=%s from step %d", esc.line_id[:12], esc.step)
        svc.count("escalations")
        texted += await start_chain(
            svc,
            line_id=esc.line_id,
            watcher_user_id=esc.watcher_user_id,
            steps=steps,
            codes=codes,
            facts=esc.facts,
            alias=esc.alias,
            tz=esc.tz,
            now=now,
            trigger="poll",
            start=esc.step + 1,
            swapped=swapped,
        )
    return texted


async def phone_recently_swapped(svc: AlertsService, phone_line_id: str, e164: str, now: datetime) -> bool:
    for w in list_watches_for_line(svc.store, phone_line_id):
        if w.last_state is not None and swap_distrusted(w.last_state.sim_change_at, now, svc.thresholds):
            return True
    hours = max(1, int(svc.thresholds.ACK_DISTRUST / timedelta(hours=1)))
    try:
        result = await svc.carrier.sim_swap_check(LineRef(phone_line_id, e164), hours)
    except CarrierError as e:
        fail_closed: bool = e.reason_code != ReasonCode.NOT_BOUND
        return fail_closed
    swapped: bool = result.swapped
    return swapped


async def handle_reply(svc: AlertsService, from_e164: str, text: str, now: datetime) -> list[str]:
    """An inbound SMS. Returns one of "accepted" / "ignored" per escalation it touched."""
    word = text.strip().upper().rstrip(".!")
    if word not in ACK_WORDS:
        svc.count("reply_not_ack")
        return []
    phone_line_id = svc.hasher.line_id(from_e164)
    targets: list[tuple[str, str]] = []
    route = S.ack_route(svc.store, phone_line_id)
    if route is not None:
        targets.append(route)
    for w in list_watches_for_line(svc.store, phone_line_id):  # a reply from the watched line itself
        if (phone_line_id, w.watcher_user_id) not in targets:
            targets.append((phone_line_id, w.watcher_user_id))
    pending = [
        e
        for e in (S.get_escalation(svc.store, line, watcher) for line, watcher in targets)
        if e is not None and not e.acked
    ]
    if not pending:
        svc.count("reply_unmatched")
        return []
    distrusted = await phone_recently_swapped(svc, phone_line_id, from_e164, now)
    results: list[str] = []
    for esc in pending:
        if distrusted:
            audit(
                svc,
                esc.line_id,
                now,
                trigger="event",
                outcome="suppressed",
                codes=[ReasonCode.ACK_IGNORED_SWAPPED_LINE],
            )
            S.save_escalation(svc.store, esc.model_copy(update={"ack_ignored": True}))
            svc.count("ack_ignored_swapped_line")
            results.append("ignored")
        else:
            audit(svc, esc.line_id, now, trigger="event", outcome="ok", codes=[ReasonCode.OK])
            S.clear_escalation(svc.store, esc.line_id, esc.watcher_user_id)
            svc.count("ack_accepted")
            results.append("accepted")
    return results
