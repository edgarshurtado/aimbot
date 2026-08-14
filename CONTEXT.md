# FitBot

Books fitness classes on aimharder.com on a member's behalf, at the moment the gym first allows it.

## Language

**Box**:
A gym on the aimharder platform, identified by a box id and a subdomain name.
_Avoid_: Gym, club, centre

**Gym Class**:
A single scheduled session at a **Box**, with a name, a start time and a spot limit.
_Avoid_: Session, activity, event

**Booking Goal**:
A member's stated intent to obtain a place in a future **Gym Class** that is not yet bookable.
_Avoid_: Booking, reservation, request

**Booking**:
A confirmed place in a **Gym Class**, held by aimharder.
_Avoid_: Reservation

**Timetable**:
The set of **Gym Classes** a **Box** has published for a given day. It exists well before the day's **Booking Window** opens — the **Box** announces what it will run long before it accepts bookings for it.
_Avoid_: Schedule, calendar, agenda

**Booking Window**:
The period during which the **Box** accepts bookings for a given **Gym Class** — it opens some fixed interval before the class starts and closes when the class begins.
_Avoid_: Booking period, availability window

**Trigger Time**:
The moment FitBot attempts to convert a **Booking Goal** into a **Booking**.
_Avoid_: Schedule time, run time, execution time

## Relationships

- A member holds zero or more **Booking Goals**
- A **Booking Goal** targets exactly one **Gym Class**
- A successful attempt at **Trigger Time** turns a **Booking Goal** into a **Booking** and discards the goal
- Every **Gym Class** has exactly one **Booking Window**
- **Trigger Time** is FitBot's *estimate* of when the **Booking Window** opens — the two are not the same thing
- A day's **Timetable** is published long before that day's **Booking Window** opens, so a member can see a **Gym Class** they cannot yet book
- No two **Gym Classes** in one **Timetable** share both a name and a start time — the pair identifies a class within its day

## Example dialogue

> **Dev:** "We fire at `class_start - days_in_advance`. So for a Thursday 19:00 class with four days in advance, that's Sunday 19:00."
> **Domain expert:** "Then you're guessing. The **Booking Window** opening is the gym's rule, not ours — if the box opens bookings at midnight four days out, we're eighteen hours late and the class is long gone. If it opens at 19:00 exactly, we're racing everyone else to the millisecond."
> **Dev:** "So **Trigger Time** and the **Booking Window** opening can disagree."
> **Domain expert:** "They can, and nothing in the system notices when they do. A booking attempt outside the window isn't an error to aimharder — it just doesn't book."

## Flagged ambiguities

- "booking" was used to mean both the member's intent and the confirmed place at the gym — resolved: **Booking Goal** is the intent, **Booking** is the confirmed place. The code's `BookingGoal` model matches; the aimharder API's `bookings` field is a list of **Gym Classes**, not **Bookings**, which is a naming collision to watch for.
- **Trigger Time** was treated as equivalent to the **Booking Window** opening — resolved: it is an estimate derived from `days_in_advance`, and its correctness is an open question, not an established fact.
- A member's *stated* class was conflated with a *real* one — resolved: a **Booking Goal** now names a **Gym Class** the member picked out of a published **Timetable**, so the class is known to exist when the goal is made. It is still not known to be *bookable*: existence and availability are separate facts.
- Open, not yet resolved: the platform appears to mark each **Gym Class** with whether it is currently bookable. If confirmed, the **Booking Window** becomes something FitBot can observe rather than estimate — which would settle the **Trigger Time** ambiguity above.
