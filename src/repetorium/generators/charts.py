"""Exhibit-reading generators. Charts are plain dicts rendered by the QML ChartView."""

import random

from repetorium.generators.base import Item, choice_item, fmt_money, fmt_num, fmt_pct, generator

SEGMENT_SETS = [
    ("Revenue by region ($M)", ["North", "South", "East", "West", "Central"]),
    ("Revenue by product line ($M)", ["Snacks", "Beverages", "Frozen", "Dairy", "Bakery"]),
    ("Sales by channel ($M)", ["Stores", "Online", "Wholesale", "Partners", "Direct"]),
]


def bar_chart(title: str, labels: list[str], values: list[float], unit: str = "$M") -> dict:
    return {"type": "bar", "title": title, "labels": labels, "unit": unit,
            "series": [{"name": title, "values": values}]}


def _segments(rng: random.Random, n: int) -> tuple[str, list[str], list[float]]:
    title, labels = rng.choice(SEGMENT_SETS)
    labels = rng.sample(labels, min(n, len(labels)))
    values = rng.sample(range(10, 130, 5), len(labels))
    return title, labels, [float(v) for v in values]


@generator("read_bar")
def read_bar(rng: random.Random, d: int, p: dict) -> Item:
    title, labels, values = _segments(rng, 3 + d)
    chart = bar_chart(title, labels, values)
    if d == 1:
        ans = max(values) - min(values)
        q = "By how much ($M) does the largest segment exceed the smallest?"
        sol = f"{fmt_num(max(values))} − {fmt_num(min(values))} = {fmt_num(ans)} $M."
    else:
        ans = sum(values)
        q = "What is the total across all segments ($M)?"
        sol = " + ".join(fmt_num(v) for v in values) + f" = {fmt_num(ans)} $M."
    return Item(prompt=f"Look at the exhibit. {q}", kind="numeric", answer=ans, unit="$M",
                tolerance=0.0, abs_tolerance=0.5, chart=chart,
                solution=sol + " Always read the title, units and axis before computing.")


@generator("chart_share")
def chart_share(rng: random.Random, d: int, p: dict) -> Item:
    title, labels, values = _segments(rng, 3 + d)
    idx = rng.randrange(len(labels))
    total = sum(values)
    ans = values[idx] / total * 100
    return Item(
        prompt=f"Look at the exhibit. What share of the total does {labels[idx]} represent?",
        kind="numeric", answer=ans, unit="%", abs_tolerance=0.5,
        chart=bar_chart(title, labels, values),
        solution=f"Total = {fmt_num(total)}. {labels[idx]} = {fmt_num(values[idx])} → "
                 f"{fmt_num(values[idx])} / {fmt_num(total)} ≈ {fmt_pct(ans)}.",
    )


@generator("chart_growth")
def chart_growth(rng: random.Random, d: int, p: dict) -> Item:
    years = [str(y) for y in range(2020, 2025)]
    base = rng.choice([40, 50, 60, 80, 100])
    vals = [float(base)]
    for _ in years[1:]:
        vals.append(round(vals[-1] * (1 + rng.choice([-0.1, 0.05, 0.1, 0.15, 0.2, 0.25])), 0))
    i, j = (0, len(years) - 1) if d >= 2 else (len(years) - 2, len(years) - 1)
    ans = (vals[j] - vals[i]) / vals[i] * 100
    return Item(
        prompt=f"Look at the exhibit. What was the total percentage growth in revenue from "
               f"{years[i]} to {years[j]}?",
        kind="numeric", answer=ans, unit="%", abs_tolerance=0.5,
        chart=bar_chart("Annual revenue ($M)", years, vals),
        solution=f"({fmt_num(vals[j])} − {fmt_num(vals[i])}) / {fmt_num(vals[i])} = {fmt_pct(ans)}.",
    )


@generator("chart_trend")
def chart_trend(rng: random.Random, d: int, p: dict) -> Item:
    years = [str(y) for y in range(2020, 2025)]
    names = rng.sample(["Product A", "Product B", "Product C", "Product D"], 3 if d < 3 else 4)
    rates = rng.sample([-0.05, 0.02, 0.06, 0.1, 0.15, 0.22], len(names))
    series = []
    for name, r in zip(names, rates, strict=True):
        start = rng.choice([30, 50, 70, 90, 110]) if d > 1 else 60
        series.append({"name": name, "values": [round(start * (1 + r) ** t, 1) for t in range(5)]})
    best = names[rates.index(max(rates))]
    return choice_item(
        rng, "Look at the exhibit. Which product grew fastest (highest CAGR) over the period?",
        best, [n for n in names if n != best],
        chart={"type": "line", "title": "Revenue by product ($M)", "labels": years,
               "unit": "$M", "series": series},
        solution=f"{best} grew at ≈{max(rates) * 100:.0f}% per year. Compare growth rates, not "
                 "absolute size — the largest line is not necessarily the fastest growing.",
    )


@generator("table_calc")
def table_calc(rng: random.Random, d: int, p: dict) -> Item:
    stores = rng.sample(["Store A", "Store B", "Store C", "Store D", "Store E"], 3 + (d > 1))
    rows, per = [], []
    for s in stores:
        customers = rng.choice([2000, 4000, 5000, 8000, 10000, 12500])
        spend = rng.choice([12, 15, 20, 25, 30, 40])
        per.append(spend)
        rows.append([s, fmt_money(customers * spend), fmt_num(customers)])
    table = {"headers": ["Store", "Monthly revenue", "Customers"], "rows": rows}
    if d == 1 or len(set(per)) < len(per):
        idx = rng.randrange(len(stores))
        return Item(
            prompt=f"Using the table, what is the average spend per customer at {stores[idx]}?",
            kind="numeric", answer=per[idx], unit="$", tolerance=0.01, table=table,
            solution=f"{rows[idx][1]} ÷ {rows[idx][2]} = {fmt_money(per[idx])}.",
        )
    best = stores[per.index(max(per))]
    return choice_item(
        rng, "Using the table, which store has the highest spend per customer?",
        best, [s for s in stores if s != best], table=table,
        solution="Divide revenue by customers for each store: "
                 + ", ".join(f"{s} {fmt_money(v)}" for s, v in zip(stores, per, strict=True)) + ".",
    )


@generator("chart_insight")
def chart_insight(rng: random.Random, d: int, p: dict) -> Item:
    years = [str(y) for y in range(2021, 2025)]
    rev0 = rng.choice([100, 120, 150])
    scenario = rng.choice(["cost_squeeze", "volume_price", "mix"])
    if scenario == "cost_squeeze":
        rev = [rev0 * (1 + 0.08 * t) for t in range(4)]
        cost = [rev0 * 0.8 * (1 + 0.15 * t) for t in range(4)]
        series = [{"name": "Revenue", "values": [round(v) for v in rev]},
                  {"name": "Costs", "values": [round(v) for v in cost]}]
        correct = "Costs are growing faster than revenue, so profit is being squeezed"
        wrong = ["Revenue decline is the main cause of falling profit",
                 "Profit is growing because revenue is rising",
                 "Costs are flat, so the issue must be pricing"]
        title = "Revenue vs costs ($M)"
    elif scenario == "volume_price":
        vol = [100, 108, 117, 126]
        price = [10, 9.4, 8.8, 8.2]
        series = [{"name": "Units (K)", "values": vol},
                  {"name": "Avg price ($ × 10)", "values": [x * 10 for x in price]}]
        correct = "Volume growth is being offset by steady price erosion"
        wrong = ["Both price and volume are declining",
                 "Price increases are driving revenue growth",
                 "Volume is stagnant while prices hold"]
        title = "Volume vs average price"
    else:
        series = [{"name": "Premium share of sales (%)", "values": [40, 34, 28, 22]},
                  {"name": "Overall margin (%)", "values": [24, 22, 20, 18]}]
        correct = "A shift in mix toward lower-margin products is diluting overall margin"
        wrong = ["Premium products are gaining share and lifting margins",
                 "Margins are falling despite a richer product mix",
                 "Mix is stable, so margin decline must come from fixed costs"]
        title = "Product mix vs margin"
    return choice_item(
        rng, "Which is the best 'so what' insight from this exhibit?", correct, wrong,
        chart={"type": "line", "title": title, "labels": years, "unit": "", "series": series},
        solution="A good insight links the trends to a business implication: " + correct.lower()
                 + ". State the implication, not just the numbers.",
    )
