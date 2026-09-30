---
status: accepted
---

# Booking Attempts consume their Booking Goal

AimBot makes one **Booking Attempt** per **Booking Goal**, at **Trigger Time**. Every attempt
discards its goal and reports the outcome to the member, whether it produced a **Booking** or
failed, and regardless of *why* it failed. The alternative — keeping the goal alive when the
failure says nothing about the goal itself — was rejected because it needs a
recoverable/unrecoverable taxonomy that has to be correct for every failure mode the platform
can produce, including ones not yet seen; a misclassification there silently resurrects the
class of bug this change exists to remove.

## Considered options

- **Discard only on a verdict.** Discard when the platform answered about this class (timetable
  empty, class not in the timetable, no credit, booking rejected); keep the goal when AimBot never
  got to ask (auth failure, timeout, malformed response). Rejected: two categories to define,
  classify and keep straight, and each new failure mode needs the right verdict at the moment it
  is introduced.
- **Retry before giving up.** Rejected: the **Booking Window** is a race, so a retry policy has no
  natural stopping rule. Worth building deliberately as its own feature, not smuggled in here.

## Consequences

- A fault entirely on AimBot's side destroys goals it could in principle have kept. If aimharder
  changes its login again, every member's every attempt raises `AuthenticationFailed`, and AimBot
  works through the store deleting every **Booking Goal**, one message at a time, for something a
  redeploy would have fixed. This is accepted knowingly, in exchange for a single code path.
- **Lapsed Booking Goals** stop accumulating: no goal outlives its attempt, so no separate cleanup
  pass is needed and `/schedule` stops listing residue.
- A **Lapsed Booking Goal** is the one case that is swept *silently* — no attempt, no message.
  Nothing failed now, so there is nothing to report.
