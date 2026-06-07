import math
from datetime import datetime, timedelta

from database import Database


def _decay(dt: datetime, half_life_days: float = 7.0) -> float:
    days = (datetime.now() - dt).total_seconds() / 86400
    return math.exp(-days * math.log(2) / half_life_days)


def _minmax_normalize(values: list[float]) -> list[float]:
    mn, mx = min(values), max(values)
    if mx == mn:
        return [0.5] * len(values)
    return [(v - mn) / (mx - mn) for v in values]


def _compute_scores(db: Database, since: datetime, clue: int | None) -> dict:
    """Compute advice scores for a given clue filter (or None for all clues)."""
    filter_clue = clue

    records = db.list_records(since=since, clue=clue)
    summary = db.get_summary(since=since)
    all_names = [s["name"] for s in summary]

    if not all_names:
        return {"scores": [], "clue_suggestions": {}}

    given = {}
    received = {}
    new_clues = {}
    last_time = {}
    total_interact = {}

    for s in summary:
        name = s["name"]
        given[name] = 0
        received[name] = 0
        new_clues[name] = 0
        last_time[name] = None
        total_interact[name] = 0

    all_records = db.list_records(since=since) if filter_clue else records

    for r in all_records if filter_clue else records:
        name = r["name"]
        total_interact[name] = total_interact.get(name, 0) + 1
        t = datetime.fromisoformat(r["time"]) if isinstance(r["time"], str) else r["time"]
        cur = last_time.get(name)
        if cur is None or t > cur:
            last_time[name] = t

    for r in records:
        name = r["name"]
        if r["type"] == "+":
            received[name] = received.get(name, 0) + 1
            if r["was_new"]:
                new_clues[name] = new_clues.get(name, 0) + 1
        else:
            given[name] = given.get(name, 0) + 1

    names = [n for n in all_names if given.get(n, 0) + received.get(n, 0) > 0] if filter_clue else list(all_names)

    if not names:
        return {"scores": [], "clue_suggestions": {}}

    reciprocity_raw = []
    scarcity_raw = []
    activity_raw = []
    frequency_raw = []
    balance_raw = []

    for name in names:
        g = given.get(name, 0)
        r = received.get(name, 0)
        total = g + r

        if total > 0:
            reciprocity_raw.append((r - g) / total)
        else:
            reciprocity_raw.append(0)

        if r > 0:
            scarcity_raw.append(new_clues.get(name, 0) / r)
        else:
            scarcity_raw.append(0)

        lt = last_time.get(name)
        activity_raw.append(_decay(lt) if lt else 0)

        frequency_raw.append(float(total_interact.get(name, 0)))

        if filter_clue:
            for s in summary:
                if s["name"] == name:
                    balance_raw.append(float(s.get(f"c{filter_clue}", 0)))
                    break
            else:
                balance_raw.append(0.0)

    reciprocity_norm = _minmax_normalize(reciprocity_raw)
    scarcity_norm = _minmax_normalize(scarcity_raw)
    activity_norm = _minmax_normalize(activity_raw)
    frequency_norm = _minmax_normalize(frequency_raw)

    scores = []
    for i, name in enumerate(names):
        row = {
            "name": name,
            "reciprocity": round(reciprocity_norm[i], 3),
            "scarcity": round(scarcity_norm[i], 3),
            "activity": round(activity_norm[i], 3),
            "frequency": round(frequency_norm[i], 3),
        }

        if filter_clue:
            bal = balance_raw[i]
            all_neg = [b for b in balance_raw if b < 0]
            max_neg = max(abs(b) for b in all_neg) if all_neg else 1
            need_score = min((-bal) / max_neg, 1.0) if bal < 0 else 0.0
            row["need"] = round(need_score, 3)
            row["clue_balance"] = round(bal, 3)
            score = (
                0.40 * need_score
                + 0.25 * row["reciprocity"]
                + 0.15 * row["activity"]
                + 0.10 * row["frequency"]
                + 0.10 * row["scarcity"]
            )
        else:
            row["clue_balance"] = None
            score = (
                0.35 * row["reciprocity"]
                + 0.30 * row["scarcity"]
                + 0.20 * row["activity"]
                + 0.15 * row["frequency"]
            )

        row["score"] = round(score, 3)
        scores.append(row)

    scores.sort(key=lambda x: x["score"], reverse=True)

    clue_suggestions = {}
    if filter_clue:
        for s in summary:
            name = s["name"]
            key = f"c{filter_clue}"
            cb = s.get(key, 0)
            if cb > 0:
                clue_suggestions[name] = cb

    return {"scores": scores, "clue_suggestions": clue_suggestions}


def get_advice(db: Database, since: datetime | None = None, clue: int | None = None, weight: float = 1.0) -> dict:
    if since is None:
        since = datetime.now() - timedelta(days=7)

    if clue and weight < 1.0:
        spec = _compute_scores(db, since, clue)
        all_ = _compute_scores(db, since, None)

        all_map = {s["name"]: s["score"] for s in all_["scores"]}
        for s in spec["scores"]:
            a = all_map.get(s["name"])
            if a is not None:
                s["score"] = round(weight * s["score"] + (1 - weight) * a, 3)

        spec["scores"].sort(key=lambda x: x["score"], reverse=True)
        return spec

    result = _compute_scores(db, since, clue)
    return {
        "scores": result["scores"],
        "clue_suggestions": result.get("clue_suggestions", {}),
    }
