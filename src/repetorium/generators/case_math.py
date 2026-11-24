"""Case-math generators: realistic business numbers chosen so mental math is feasible."""

import random

from repetorium.generators.base import (
    Item,
    choice_item,
    fmt_big,
    fmt_money,
    fmt_num,
    fmt_pct,
    generator,
)

COMPANIES = [
    "a regional grocery chain", "a mid-sized airline", "a specialty coffee roaster",
    "a B2B software firm", "a hospital network", "a sportswear brand", "a cement producer",
    "an online furniture retailer", "a pharmacy chain", "a fintech lender",
]


def _company(rng: random.Random) -> str:
    return rng.choice(COMPANIES)


def _scaled(rng: random.Random, mantissas: list[float], exps: list[int]) -> float:
    return rng.choice(mantissas) * 10 ** rng.choice(exps)


@generator("pct_of")
def pct_of(rng: random.Random, d: int, p: dict) -> Item:
    pct = rng.choice({1: [10, 20, 25, 50, 5], 2: [15, 12.5, 35, 40, 7.5], 3: [17, 23, 37, 64, 8.5]}[d])
    base = _scaled(rng, [1.2, 2.4, 3.6, 4.8, 6, 8, 1.6, 7.2], [5, 6, 7, 8])
    ans = base * pct / 100
    channel = rng.choice(["online", "from repeat customers", "from its top region", "from services"])
    return Item(
        prompt=f"{_company(rng).capitalize()} has revenue of {fmt_money(base)}. "
               f"{fmt_pct(pct)} of revenue comes {channel}. How much revenue is that?",
        kind="numeric", answer=ans, unit="$",
        solution=f"{fmt_pct(pct)} × {fmt_money(base)} = {fmt_money(ans)}. "
                 f"Tip: split {pct}% into easy pieces (10%, 5%, 1%) and add them up.",
    )


@generator("pct_change")
def pct_change(rng: random.Random, d: int, p: dict) -> Item:
    old = _scaled(rng, [1.2, 2, 2.4, 4, 5, 8], [6, 7])
    change = rng.choice({1: [10, 20, 25, -10, -20, 50], 2: [15, -15, 30, -25, 12.5],
                         3: [-12.5, 17.5, -35, 22.5, 7.5]}[d])
    new = old * (1 + change / 100)
    metric = rng.choice(["revenue", "operating profit", "the cost base", "marketing spend"])
    return Item(
        prompt=f"{_company(rng).capitalize()}'s {metric} went from {fmt_money(old)} last year "
               f"to {fmt_money(new)} this year. What is the percentage change? "
               f"(Use a negative number for a decline.)",
        kind="numeric", answer=change, unit="%", abs_tolerance=0.3,
        solution=f"(New − Old) / Old = ({fmt_money(new)} − {fmt_money(old)}) / {fmt_money(old)} "
                 f"= {fmt_pct(change)}.",
    )


@generator("big_mult")
def big_mult(rng: random.Random, d: int, p: dict) -> Item:
    units = _scaled(rng, [1.5, 2, 2.5, 3, 4, 6, 1.2], {1: [3, 4], 2: [5, 6], 3: [6, 7]}[d])
    price = rng.choice({1: [20, 40, 50, 5], 2: [12, 25, 35, 80, 150], 3: [18, 45, 120, 2.5, 750]}[d])
    product = rng.choice(["subscriptions", "units", "tickets", "policies", "meals"])
    ans = units * price
    return Item(
        prompt=f"{_company(rng).capitalize()} sells {fmt_big(units)} {product} per year "
               f"at an average price of {fmt_money(price)}. What is annual revenue?",
        kind="numeric", answer=ans, unit="$",
        solution=f"{fmt_big(units)} × {fmt_money(price)} = {fmt_money(ans)}. "
                 "Multiply the leading digits first, then count the zeros.",
    )


@generator("big_div")
def big_div(rng: random.Random, d: int, p: dict) -> Item:
    per = rng.choice({1: [20, 50, 100, 200], 2: [25, 40, 150, 250, 400], 3: [35, 120, 480, 1250]}[d])
    count = _scaled(rng, [1.2, 2, 2.4, 3, 4.8, 6], [4, 5, 6])
    total = per * count
    return Item(
        prompt=f"{_company(rng).capitalize()} generated {fmt_money(total)} of revenue from "
               f"{fmt_big(count)} customers. What is the average revenue per customer?",
        kind="numeric", answer=per, unit="$",
        solution=f"{fmt_money(total)} ÷ {fmt_big(count)} = {fmt_money(per)}. "
                 "Cancel zeros first (e.g. B ÷ M leaves a factor of 1,000).",
    )


@generator("mental_estimate")
def mental_estimate(rng: random.Random, d: int, p: dict) -> Item:
    a = rng.randint(11, 99) * 10 ** rng.choice([0, 1, 2])
    b = rng.randint(11, 99) * 10 ** rng.choice({1: [1], 2: [1, 2], 3: [2, 3]}[d])
    ans = a * b
    distractors = [ans * 10, ans / 10, ans * rng.choice([2.5, 3, 4])]
    return choice_item(
        rng, f"Without a calculator, which is closest to {fmt_num(a)} × {fmt_num(b)}?",
        fmt_big(ans), [fmt_big(x) for x in distractors],
        solution=f"Round each factor ({fmt_num(a)} ≈ {fmt_num(round(a, -len(str(a)) + 1))}, "
                 f"{fmt_num(b)} ≈ {fmt_num(round(b, -len(str(b)) + 1))}), multiply, and fix the "
                 f"order of magnitude. The exact answer is {fmt_num(ans)}.",
    )


@generator("unit_rates")
def unit_rates(rng: random.Random, d: int, p: dict) -> Item:
    per_hour = rng.choice([20, 30, 40, 60, 25, 45])
    hours = rng.choice([8, 10, 12, 16])
    days = rng.choice({1: [300], 2: [300, 350, 360], 3: [250, 310, 360]}[d])
    price = rng.choice({1: [5, 10], 2: [4, 8, 12], 3: [3.5, 6.5, 15]}[d])
    ans = per_hour * hours * days * price
    shop = rng.choice(["A car wash", "A busy café", "A parking garage", "A fast-food outlet"])
    return Item(
        prompt=f"{shop} serves {per_hour} customers per hour, is open {hours} hours a day and "
               f"{days} days a year. Each customer spends {fmt_money(price)}. "
               "What is its annual revenue?",
        kind="numeric", answer=ans, unit="$",
        solution=f"{per_hour} × {hours} × {days} × {fmt_money(price)} = {fmt_money(ans)}. "
                 "Convert to a common time unit before multiplying.",
    )


@generator("weighted_avg")
def weighted_avg(rng: random.Random, d: int, p: dict) -> Item:
    n = 2 if d == 1 else 3
    shares = rng.choice([[50, 50], [60, 40], [75, 25], [80, 20]] if n == 2
                        else [[50, 30, 20], [40, 40, 20], [60, 30, 10], [50, 25, 25]])
    margins = rng.sample([10, 15, 20, 25, 30, 40, 50, 5], n)
    ans = sum(s * m for s, m in zip(shares, margins, strict=True)) / 100
    segs = rng.sample(["Retail", "Wholesale", "Online", "Services", "Enterprise", "SMB"], n)
    lines = "; ".join(f"{s}: {sh}% of revenue at {m}% margin"
                      for s, sh, m in zip(segs, shares, margins, strict=True))
    return Item(
        prompt=f"A company's revenue mix is — {lines}. What is the blended profit margin?",
        kind="numeric", answer=ans, unit="%", abs_tolerance=0.2,
        solution=" + ".join(f"{sh}%×{m}%" for sh, m in zip(shares, margins, strict=True))
                 + f" = {fmt_pct(ans)}. Blended margin is a revenue-weighted average.",
    )


@generator("compound_growth")
def compound_growth(rng: random.Random, d: int, p: dict) -> Item:
    start = _scaled(rng, [1, 2, 4, 5, 8], [8, 9])
    g = rng.choice({1: [10, 20, 50], 2: [5, 10, 15, 20], 3: [7, 12, 25, -10]}[d])
    n = rng.choice({1: [2], 2: [2, 3], 3: [3, 4]}[d])
    ans = start * (1 + g / 100) ** n
    return Item(
        prompt=f"A market is worth {fmt_money(start)} today and grows {fmt_pct(g)} per year. "
               f"How big will it be in {n} years?",
        kind="numeric", answer=ans, unit="$", tolerance=0.03,
        solution=f"{fmt_money(start)} × (1 + {g / 100:g})^{n} = {fmt_money(ans)}. "
                 "Grow year by year; don't simply add n × g%.",
    )


@generator("cagr")
def cagr(rng: random.Random, d: int, p: dict) -> Item:
    g = rng.choice({1: [10, 20, 50, 100], 2: [5, 10, 15, 20, 25], 3: [8, 12, 18, 30]}[d])
    n = rng.choice({1: [2], 2: [2, 3, 4], 3: [3, 5]}[d])
    start = _scaled(rng, [1, 2, 4, 5], [7, 8])
    end = start * (1 + g / 100) ** n
    return Item(
        prompt=f"Sales grew from {fmt_money(start)} to {fmt_money(end)} over {n} years. "
               "Approximately what was the compound annual growth rate (CAGR)?",
        kind="numeric", answer=g, unit="%", abs_tolerance=0.5,
        solution=f"CAGR = (End/Start)^(1/{n}) − 1 = ({fmt_num(end / start, 3)})^(1/{n}) − 1 "
                 f"≈ {fmt_pct(g)}. Sanity check with the rule of 72: doubling time ≈ 72 / CAGR.",
    )


@generator("margin")
def margin(rng: random.Random, d: int, p: dict) -> Item:
    revenue = _scaled(rng, [2, 4, 5, 8, 1.2, 2.4], [6, 7, 8])
    m = rng.choice({1: [10, 20, 25, 50], 2: [15, 12.5, 30, 40, 8], 3: [17.5, 22, 6.5, 35]}[d])
    cost = revenue * (1 - m / 100)
    return Item(
        prompt=f"{_company(rng).capitalize()} had revenue of {fmt_money(revenue)} and total "
               f"costs of {fmt_money(cost)}. What is its profit margin?",
        kind="numeric", answer=m, unit="%", abs_tolerance=0.3,
        solution=f"Profit = {fmt_money(revenue)} − {fmt_money(cost)} = {fmt_money(revenue - cost)}. "
                 f"Margin = Profit / Revenue = {fmt_pct(m)}.",
    )


@generator("markup_margin")
def markup_margin(rng: random.Random, d: int, p: dict) -> Item:
    pairs = {1: [(25, 20), (100, 50), (50, 100 / 3)], 2: [(25, 20), (60, 37.5), (150, 60)],
             3: [(20, 50 / 3), (40, 200 / 7), (300, 75)]}[d]
    markup, mrg = rng.choice(pairs)
    if d == 3 and rng.random() < 0.5:
        return Item(
            prompt=f"A retailer targets a {fmt_pct(mrg)} gross margin on selling price. "
                   "What markup on cost does that require?",
            kind="numeric", answer=markup, unit="%", abs_tolerance=0.5,
            solution=f"Markup = Margin / (1 − Margin) = {mrg / 100:.3f} / {1 - mrg / 100:.3f} "
                     f"= {fmt_pct(markup)}.",
        )
    return Item(
        prompt=f"A distributor prices products at a {fmt_pct(markup)} markup on cost. "
               "What is its gross margin as a percentage of selling price?",
        kind="numeric", answer=mrg, unit="%", abs_tolerance=0.5,
        solution=f"Margin = Markup / (1 + Markup) = {markup / 100:g} / {1 + markup / 100:g} "
                 f"= {fmt_pct(mrg)}. Markup is on cost; margin is on price.",
    )


@generator("contribution")
def contribution(rng: random.Random, d: int, p: dict) -> Item:
    price = rng.choice([20, 40, 50, 80, 100, 120, 250])
    parts = {"materials": 0.3, "direct labour": 0.15, "shipping": 0.05, "sales commission": 0.1}
    names = rng.sample(list(parts), 2 if d == 1 else 3 if d == 2 else 4)
    costs = {n: round(price * parts[n] * rng.choice([0.8, 1, 1.2]), 1) for n in names}
    unit_cm = price - sum(costs.values())
    ask_pct = d >= 2 and rng.random() < 0.5
    cost_text = ", ".join(f"{n} {fmt_money(c)}" for n, c in costs.items())
    sol = (f"Contribution = Price − variable costs = {fmt_money(price)} − "
           f"{fmt_money(sum(costs.values()))} = {fmt_money(unit_cm)}.")
    if ask_pct:
        ans = unit_cm / price * 100
        return Item(
            prompt=f"A product sells for {fmt_money(price)}. Variable costs per unit: {cost_text}. "
                   "What is the contribution margin as a % of price?",
            kind="numeric", answer=ans, unit="%", abs_tolerance=0.5,
            solution=sol + f" As a % of price: {fmt_pct(ans)}.",
        )
    return Item(
        prompt=f"A product sells for {fmt_money(price)}. Variable costs per unit: {cost_text}. "
               "What is the contribution per unit?",
        kind="numeric", answer=unit_cm, unit="$", tolerance=0.01, solution=sol,
    )


@generator("breakeven")
def breakeven(rng: random.Random, d: int, p: dict) -> Item:
    cm = rng.choice({1: [5, 10, 20, 25], 2: [4, 8, 12, 15, 40], 3: [6, 7.5, 18, 35]}[d])
    vc = rng.choice([5, 10, 15, 20, 30, 45])
    units = _scaled(rng, [1, 2, 2.5, 4, 5, 6], [4, 5, 6])
    fixed = cm * units
    return Item(
        prompt=f"A new plant has annual fixed costs of {fmt_money(fixed)}. Each unit sells for "
               f"{fmt_money(vc + cm)} and costs {fmt_money(vc)} in variable cost. How many units "
               "must it sell per year to break even?",
        kind="numeric", answer=units, unit="units",
        solution=f"Contribution per unit = {fmt_money(vc + cm)} − {fmt_money(vc)} = {fmt_money(cm)}. "
                 f"Break-even = Fixed / Contribution = {fmt_money(fixed)} / {fmt_money(cm)} "
                 f"= {fmt_big(units)} units.",
    )


@generator("payback")
def payback(rng: random.Random, d: int, p: dict) -> Item:
    years = rng.choice({1: [2, 4, 5], 2: [2.5, 3, 4, 8], 3: [1.5, 3.5, 6.25]}[d])
    savings = _scaled(rng, [1, 2, 4, 5, 8], [5, 6])
    upkeep = savings * rng.choice([0.2, 0.25]) if d == 3 else 0
    invest = (savings - upkeep) * years
    extra = f" but adds {fmt_money(upkeep)} of yearly maintenance" if upkeep else ""
    return Item(
        prompt=f"An automation project costs {fmt_money(invest)} upfront. It saves "
               f"{fmt_money(savings)} per year{extra}. What is the payback period in years?",
        kind="numeric", answer=years, unit="years", abs_tolerance=0.05,
        solution=f"Net annual benefit = {fmt_money(savings - upkeep)}. Payback = "
                 f"{fmt_money(invest)} / {fmt_money(savings - upkeep)} = {fmt_num(years)} years.",
    )


@generator("roi")
def roi(rng: random.Random, d: int, p: dict) -> Item:
    cost = _scaled(rng, [1, 2, 4, 5, 8], [5, 6])
    r = rng.choice({1: [50, 100, 25], 2: [20, 150, 75, -20], 3: [35, 12.5, 220, -40]}[d])
    gain = cost * (1 + r / 100)
    return Item(
        prompt=f"A marketing campaign cost {fmt_money(cost)} and generated {fmt_money(gain)} of "
               "incremental gross profit. What was its ROI?",
        kind="numeric", answer=r, unit="%", abs_tolerance=0.5,
        solution=f"ROI = (Gain − Cost) / Cost = ({fmt_money(gain)} − {fmt_money(cost)}) / "
                 f"{fmt_money(cost)} = {fmt_pct(r)}.",
    )


@generator("perpetuity")
def perpetuity(rng: random.Random, d: int, p: dict) -> Item:
    cf = _scaled(rng, [1, 2, 3, 4, 5, 6], [6, 7])
    r = rng.choice([8, 10, 12, 15, 20])
    g = rng.choice([2, 3, 5]) if d >= 2 else 0
    ans = cf / ((r - g) / 100)
    growth = f", growing {g}% per year forever," if g else " forever"
    return Item(
        prompt=f"A business generates {fmt_money(cf)} of free cash flow next year{growth}. "
               f"With a {r}% discount rate, what is it worth today?",
        kind="numeric", answer=ans, unit="$",
        solution=f"Value = CF / (r − g) = {fmt_money(cf)} / ({r}% − {g}%) = {fmt_money(ans)}.",
    )


@generator("npv")
def npv(rng: random.Random, d: int, p: dict) -> Item:
    factors = [0.91, 0.83, 0.75, 0.68, 0.62]
    n = {1: 2, 2: 3, 3: 4}[d]
    cf = _scaled(rng, [1, 2, 4, 5], [6])
    invest = cf * rng.choice([1.5, 2, 2.5, 3])
    pv = cf * sum(factors[:n])
    ans = pv - invest
    df_text = ", ".join(f"Y{i + 1}: {f}" for i, f in enumerate(factors[:n]))
    return Item(
        prompt=f"A project costs {fmt_money(invest)} today and returns {fmt_money(cf)} at the end "
               f"of each of the next {n} years. Discount factors at 10%: {df_text}. What is the NPV?",
        kind="numeric", answer=ans, unit="$", tolerance=0.02, abs_tolerance=0.001 * invest,
        solution=f"PV of inflows = {fmt_money(cf)} × {fmt_num(sum(factors[:n]))} = {fmt_money(pv)}. "
                 f"NPV = {fmt_money(pv)} − {fmt_money(invest)} = {fmt_money(ans)}.",
    )


@generator("market_share")
def market_share(rng: random.Random, d: int, p: dict) -> Item:
    market = _scaled(rng, [1, 2, 4, 5, 8], [8, 9, 10])
    share = rng.choice({1: [10, 20, 25, 50], 2: [5, 12.5, 15, 30, 40], 3: [3, 7.5, 18, 35]}[d])
    rev = market * share / 100
    return Item(
        prompt=f"The total market is {fmt_money(market)}. Our client's revenue is {fmt_money(rev)}. "
               "What is its market share?",
        kind="numeric", answer=share, unit="%", abs_tolerance=0.2,
        solution=f"Share = {fmt_money(rev)} / {fmt_money(market)} = {fmt_pct(share)}.",
    )


@generator("profit_scenario")
def profit_scenario(rng: random.Random, d: int, p: dict) -> Item:
    price = rng.choice([10, 20, 40, 50, 100])
    vc = price * rng.choice([0.4, 0.5, 0.6])
    vol = _scaled(rng, [1, 2, 4, 5], [5, 6])
    fixed = (price - vc) * vol * rng.choice([0.5, 0.6, 0.75])
    dp = rng.choice({1: [10], 2: [10, 20], 3: [5, 15, -10]}[d])
    dv = rng.choice({1: [-10], 2: [-5, -10, -20], 3: [-15, 10, -25]}[d])
    p1, v1 = price * (1 + dp / 100), vol * (1 + dv / 100)
    base = (price - vc) * vol - fixed
    new = (p1 - vc) * v1 - fixed
    return Item(
        prompt=f"A product sells {fmt_big(vol)} units at {fmt_money(price)} with variable cost "
               f"{fmt_money(vc)}/unit and fixed costs {fmt_money(fixed)}. If price changes by "
               f"{dp:+g}% and volume by {dv:+g}%, what is the new profit?",
        kind="numeric", answer=new, unit="$", tolerance=0.02,
        solution=f"Base profit = ({fmt_money(price)} − {fmt_money(vc)}) × {fmt_big(vol)} − "
                 f"{fmt_money(fixed)} = {fmt_money(base)}. New price {fmt_money(p1)}, volume "
                 f"{fmt_big(v1)} → ({fmt_money(p1)} − {fmt_money(vc)}) × {fmt_big(v1)} − "
                 f"{fmt_money(fixed)} = {fmt_money(new)}.",
    )
