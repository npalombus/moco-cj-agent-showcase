"""The Poisson fallback and the fit line: docs/S3S-DESIGN.md S3 ("If it does not converge or
the spread estimate is not above zero: Poisson with the same terms and robust standard
errors (sandwich::vcovHC(type = "HC1")), and the result says which was used"; the fit note:
the total of the last six months used divided by what the model expected, outside 0.90 to
1.10 the fit line) and S5.2 (the fit line's exact words).

The fallback fixture (stats_edges, batch P) has monthly counts set to their expected values:
no spread beyond Poisson; R's glm.nb does not converge on it (kit-log/raw/S3S-A-r-crosscheck
.txt: "estimate truncated at zero; iteration limit reached"). "The result says so" is read as
R's result.json naming the Poisson model; `details` naming it is in
test_s3s_details_script.py.

Fit lines (window January 2021 to August 2026 for districts 4 and 5; 2021 to 2025 for the
others): district 4's last six months were set to 0.60 of expected, district 5's to 1.60;
the ratio R gives is the fitted model's, as the truth's.
"""
import json
import re

import pytest

import s3ssupport as T
from s3sagent import (EDGES, StatsEnv, answered, ask_case, assert_estimates, result_of,
                      result_text)

FIT_LINES = {  # by hand from S5.2, ratios from the R cross-check
    "trend_d4_p6": "The last six months were about 25.2% below the trend line, so a straight "
                   "line describes the recent period poorly.",
    "trend_d5_p6": "The last six months were about 23.8% above the trend line, so a straight "
                   "line describes the recent period poorly.",
    "trend_d1": "The last six months were about 12.1% above the trend line, so a straight line "
                "describes the recent period poorly.",
}
NO_FIT_LINE = ["trend_all", "trend_all_p6", "trend_d2", "trend_d3"]


def test_the_truth_of_the_fit_ratios():
    """No program code: outside the band exactly for the cases with a fit line."""
    for name, line in FIT_LINES.items():
        t = T.truth(name)
        assert t["fit_line"], name
        assert re.fullmatch(T.fit_line_re(t["fit_ratio"]), line), name
    for name in NO_FIT_LINE:
        assert not T.truth(name)["fit_line"], name
    assert T.truth("trend_fallback")["model"] == "poisson"


def _numbers(node):
    if isinstance(node, bool):
        return []
    if isinstance(node, (int, float)):
        return [float(node)]
    if isinstance(node, dict):
        return [x for v in node.values() for x in _numbers(v)]
    if isinstance(node, list):
        return [x for v in node for x in _numbers(v)]
    return []


@pytest.mark.needs_r
def test_the_poisson_fallback(tmp_path, monkeypatch):
    """S3: the negative binomial cannot be fitted to batch P, so Poisson with HC1 is used:
    its estimate and interval equal the truth (statsmodels Poisson, HC0 x n / (n - k)); the
    result says Poisson was used."""
    env = StatsEnv(tmp_path, monkeypatch, names=(EDGES,))
    reply = answered(ask_case(env, "trend_fallback", text="I found that {a1.trend}."))
    assert_estimates(env, "trend_fallback")
    text = result_text(env)
    assert "poisson" in text, text[:500]
    assert "negative binomial" not in text.replace("not negative binomial", ""), text[:500]
    assert "{a1" not in reply.text


@pytest.mark.needs_r
@pytest.mark.parametrize("name", list(FIT_LINES) + NO_FIT_LINE)
def test_the_fit_line_exactly_when_outside_the_band(tmp_path, monkeypatch, name):
    """S3 and S5.2: R's fit ratio is the truth's (within 0.0005); the fit line is in the reply
    exactly when the ratio is outside 0.90 to 1.10, with the right percentage and side."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, name))
    t = T.truth(name)
    assert any(abs(x - t["fit_ratio"]) <= T.TOL_RATIO for x in _numbers(result_of(env))), \
        f"no fit ratio near {t['fit_ratio']:.6f} in result.json: {json.dumps(result_of(env))[:600]}"
    lines = [line for line in reply.text.split("\n") if "The last six months" in line]
    if t["fit_line"]:
        assert re.search(T.fit_line_re(t["fit_ratio"]), reply.text), reply.text
        assert reply.text.count("The last six months") == 1
    else:
        assert not lines and "The last six months" not in reply.text, reply.text
