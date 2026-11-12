"""
real_only.py  —  the desk shows the market, or it shows nothing.

He said it in one line: *"I dnt want anything in demo henceforth. All real things. This is
real money."* This module is that sentence made unavoidable.

THE PROBLEM WITH DEMO DATA is not that it is wrong. Everybody knows the demo is wrong.
The problem is that a fabricated number is SHAPED like an answer. It has two decimals, it
sits under a label that says PREMIUM, it lands next to a BUY button, and by the time it
reaches the eye it has lost every mark of where it came from. The banner at the top of the
page said "not one number here is real" and four tickets below it still quoted an entry, a
stop and a target to the paisa. Reading is not a safety mechanism. At 9:20am with the
market open, a banner is decoration and the number is the thing you act on.

So the default flips. Synthetic data is REFUSED, not labelled:

    allowed()            -> False, unless this process was explicitly launched for testing
    require("a chain")   -> raises Synthetic if it is not

There is exactly one way to turn it on - the environment variable DESK_SYNTHETIC=1, set by
a test harness at launch. Deliberately NOT a config setting: config.py is edited by hand,
persists across sessions, and a flag that can be left on by accident is not a switch, it is
a trap. An environment variable dies with the process that set it.

THE INVARIANT, which is the part that actually protects money:

    a process that is allowed to invent a number may never send an order.

broker.place() asks this module before every send. So even in a test run - which walks the
whole option layer on synthetic quotes - there is no code path from a made-up premium to a
real order. Not "we check the symbol prefix"; the fabrication itself is the disqualifier.
The DEMO: prefix guard stays as a second line, because two independent guards fail
independently and one guard defeated by a placeholder is what dead-buttons taught us.

WHAT THE PAGE DOES INSTEAD, with no token: it renders its chrome, and every panel that
would have held a number says what is missing and the command that fixes it. An empty
board is a true statement about the world. A full board of invented numbers is not.
"""
import os

ENV = "DESK_SYNTHETIC"

#: the one-line instruction that replaces every fabricated panel
FIX = "Run the '1 - START DAY' icon to log in."


class Synthetic(RuntimeError):
    """Raised when something would have to be invented to answer."""


def allowed():
    """May this process fabricate market data? False on his desk, always."""
    return os.environ.get(ENV, "").strip() == "1"


def require(what):
    """Fabricating `what` is about to happen. Refuse unless this is a test process."""
    if not allowed():
        raise Synthetic(
            f"{what} would be synthetic, and this desk trades real money. {FIX}")


def refuse(what):
    """Same rule, as a value instead of an exception: (ok, reason)."""
    if allowed():
        return True, None
    return False, f"{what} needs live data. {FIX}"


def why_no_orders():
    """Non-None when this process is disqualified from sending orders, with the reason."""
    if allowed():
        return (f"{ENV}=1 - this process is permitted to fabricate market data, so it is "
                f"not permitted to send orders. Nothing here reaches an exchange.")
    return None


def banner():
    """The single line the page shows when it has no token. Not a paragraph."""
    if allowed():
        return (f"⚠ {ENV}=1 — SYNTHETIC DATA, TEST PROCESS. Orders are disabled at the "
                f"broker, not just on the screen.")
    return None
