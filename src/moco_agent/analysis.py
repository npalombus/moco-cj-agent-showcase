"""Comparing counts: the second approved operation (design P1A, A6; decision D-031).

Python compares totals it counted itself; the model only names which results to compare.
No rate and no percentage: the highest, the lowest, and the difference between them.
"""


def join_and(items):
    """`A`, `A and B`, `A, B and C`."""
    items = [str(item) for item in items]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def age_wording(code, registry):
    return "all ages" if code is None else registry.age_groups[code]


def compare_counts(counts, registry):
    """`counts`: a list, in the order compared, of {"year", "age_group" (code or None),
    "total"}. Labels: the year when only the years differ, the age wording when only the
    age groups differ, `<year>, <age wording>` when both do. Ties are joined in compare
    order; all equal gives every label on both sides and a difference of 0."""
    years = {c["year"] for c in counts}
    groups = {c["age_group"] for c in counts}

    def label(c):
        if len(groups) == 1:
            return str(c["year"])
        if len(years) == 1:
            return age_wording(c["age_group"], registry)
        return f"{c['year']}, {age_wording(c['age_group'], registry)}"

    totals = [c["total"] for c in counts]
    top, bottom = max(totals), min(totals)
    return {"top_label": join_and([label(c) for c in counts if c["total"] == top]),
            "top_value": top,
            "bottom_label": join_and([label(c) for c in counts if c["total"] == bottom]),
            "bottom_value": bottom,
            "difference": top - bottom,
            "all_equal": top == bottom}
