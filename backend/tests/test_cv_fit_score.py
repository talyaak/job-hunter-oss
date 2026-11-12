import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / ".claude" / "skills" / "cv-optimizer" / "scripts" / "fit_score.py"
spec = importlib.util.spec_from_file_location("fit_score", SCRIPT)
fit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fit)

DIMS = {"must_haves": 35, "keywords": 65, "experience": 40, "tools": 35, "domain": 75}


def test_weighted_total_is_correct_where_an_llm_once_slipped():
    # 35*.35 + 65*.15 + 40*.20 + 35*.20 + 75*.10 = 44.5 (a model reported 46.5 for these inputs)
    assert fit.weighted_score(DIMS) == pytest.approx(44.5)
    assert fit.score(DIMS, None, [])["total"] == 44.5


def test_custom_weights_are_normalised():
    total = fit.weighted_score(DIMS, {"must_haves": 70, "keywords": 30, "experience": 0, "tools": 0, "domain": 0})
    assert total == pytest.approx((35 * 70 + 65 * 30) / 100)


def test_decision_rule():
    assert fit.decide(78, [])[0] == "proceed"
    assert fit.decide(44.5, [])[0] == "stretch"
    assert fit.decide(85, ["needs security clearance"])[0] == "proceed_with_caution"
    assert fit.decide(30, ["needs security clearance"])[0] == "skip_or_stretch"


def test_validation():
    with pytest.raises(ValueError):
        fit.weighted_score({"must_haves": 50})
    with pytest.raises(ValueError):
        fit.weighted_score({**DIMS, "tools": 120})


def test_tenure_phrases():
    assert fit.tenure("2023-01", "2026-11")["cv_phrase"] == "nearly 4 years"
    assert fit.tenure("2023-01", "2026-03")["cv_phrase"] == "3+ years"
    assert fit.tenure("2023-01", "2026-01")["cv_phrase"] == "3 years"
    assert fit.tenure("2025-09", "2026-01")["cv_phrase"] == "4 months"
    with pytest.raises(ValueError):
        fit.tenure("2026-01", "2025-01")


def test_cli_json_output(capsys):
    code = fit.main(["score", "--dims", "must_haves=100,keywords=100,experience=100,tools=100,domain=100"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["total"] == 100 and out["decision"] == "proceed"
    assert fit.main(["score", "--dims", "must_haves=1"]) == 2
