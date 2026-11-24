"""Guesstimate generators: the learner computes from stated assumptions, or finds a broken step."""

import random

from repetorium.generators.base import Item, choice_item, fmt_big, fmt_money, fmt_num, generator

# Each factor: (label, candidate values, is_money). The product of all factors is the answer.
TOP_DOWN = [
    ("annual spend on takeaway coffee in a city", [
        ("Population", [4e6, 6e6, 8e6], False),
        ("Share of adults", [0.75, 0.8], False),
        ("Share who buy coffee out daily", [0.2, 0.25, 0.3], False),
        ("Cups per day", [1, 1.5], False),
        ("Days per year", [300, 350], False),
        ("Price per cup", [3, 4, 5], True),
    ]),
    ("annual market for pet food in a country", [
        ("Households", [20e6, 25e6, 40e6], False),
        ("Share of households with a dog", [0.3, 0.4], False),
        ("Dogs per dog-owning household", [1.2, 1.5], False),
        ("Spend per dog per month", [30, 40, 50], True),
        ("Months per year", [12], False),
    ]),
    ("annual market for school backpacks in a country", [
        ("Population", [50e6, 80e6, 120e6], False),
        ("Share aged 5–18", [0.18, 0.2], False),
        ("Backpacks per student per year", [0.5, 0.75], False),
        ("Average price", [25, 30, 40], True),
    ]),
    ("annual revenue of ride-hailing in a metro area", [
        ("Population", [5e6, 10e6], False),
        ("Share who use ride-hailing", [0.2, 0.3, 0.4], False),
        ("Rides per user per month", [2, 4, 5], False),
        ("Months per year", [12], False),
        ("Average fare", [10, 12, 15], True),
    ]),
]

BOTTOM_UP = [
    ("annual revenue of hair salons in a city", [
        ("Number of salons", [800, 1200, 2000], False),
        ("Chairs per salon", [4, 5, 6], False),
        ("Customers per chair per day", [6, 8], False),
        ("Utilisation", [0.6, 0.7, 0.75], False),
        ("Open days per year", [300, 310], False),
        ("Average ticket", [20, 25, 30], True),
    ]),
    ("annual revenue of a city's cinemas", [
        ("Number of screens", [150, 200, 300], False),
        ("Shows per screen per day", [4, 5], False),
        ("Seats per screen", [150, 200], False),
        ("Average occupancy", [0.3, 0.35, 0.4], False),
        ("Days per year", [365], False),
        ("Average ticket price", [8, 10, 12], True),
    ]),
    ("annual capacity revenue of EV fast chargers on a highway network", [
        ("Charging stations", [200, 400, 500], False),
        ("Chargers per station", [4, 6, 8], False),
        ("Sessions per charger per day", [8, 10, 12], False),
        ("Days per year", [365], False),
        ("Revenue per session", [15, 20, 25], True),
    ]),
]


def _fmt_factor(v: float, money: bool) -> str:
    if money:
        return fmt_money(v)
    if v < 1 and v > 0:
        return f"{v * 100:g}%"
    return fmt_big(v)


def _instantiate(rng: random.Random, factors: list, d: int) -> list[tuple[str, float, bool]]:
    chosen = [(label, rng.choice(vals), money) for label, vals, money in factors]
    if d == 1:
        drop = [i for i, (lbl, _, m) in enumerate(chosen) if not m and i > 0 and "year" not in lbl]
        for i in reversed(drop[: max(0, len(chosen) - 4)]):
            chosen.pop(i)
    return chosen


def _estimate_item(rng: random.Random, d: int, bank: list, approach: str) -> Item:
    target, factors = rng.choice(bank)
    chosen = _instantiate(rng, factors, d)
    total = 1.0
    for _, v, _ in chosen:
        total *= v
    table = {"headers": ["Assumption", "Value"],
             "rows": [[lbl, _fmt_factor(v, m)] for lbl, v, m in chosen]}
    chain = " × ".join(_fmt_factor(v, m) for _, v, m in chosen)
    return Item(
        prompt=f"Estimate the {target} ({approach}) using the assumptions in the table.",
        kind="numeric", answer=total, unit="$", tolerance=0.03, table=table,
        solution=f"{chain} = {fmt_money(total)}. Round as you go and keep track of zeros; "
                 "state each assumption out loud in an interview.",
    )


@generator("top_down")
def top_down(rng: random.Random, d: int, p: dict) -> Item:
    return _estimate_item(rng, d, TOP_DOWN, "top-down, demand side")


@generator("bottom_up")
def bottom_up(rng: random.Random, d: int, p: dict) -> Item:
    return _estimate_item(rng, d, BOTTOM_UP, "bottom-up, supply side")


@generator("estimate_error")
def estimate_error(rng: random.Random, d: int, p: dict) -> Item:
    target, factors = rng.choice(TOP_DOWN + BOTTOM_UP)
    chosen = [(label, rng.choice(vals), money) for label, vals, money in factors]
    bad = rng.randrange(1, len(chosen))
    factor = rng.choice([10, 0.1]) if d < 3 else rng.choice([10, 0.1, 100])
    running, steps = 1.0, []
    for i, (lbl, v, m) in enumerate(chosen):
        running *= v
        shown = running * factor if i >= bad else running
        steps.append(f"× {lbl} ({_fmt_factor(v, m)}) → {fmt_num(shown) if shown < 1e4 else fmt_big(shown)}")
    steps[0] = steps[0].replace("× ", "", 1)
    labels = [f"Step {i + 1}: {s}" for i, s in enumerate(steps)]
    return choice_item(
        rng, f"A candidate estimated the {target}. Their running totals are shown below. "
             "At which step did they first make an arithmetic error?\n\n" + "\n".join(labels),
        f"Step {bad + 1}", [f"Step {i + 1}" for i in range(1, len(chosen)) if i != bad][:3],
        solution=f"At step {bad + 1} the running total is off by a factor of {fmt_num(factor)}. "
                 "Re-check orders of magnitude after every multiplication.",
    )
