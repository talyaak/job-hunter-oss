from app.filter.evaluation import (
    DimensionScores,
    ExtractedRequirements,
    LlmEvaluation,
    ScoreDimension,
    calculate_final_score,
    to_pipeline_result,
)


def test_weighted_final_score():
    scores = DimensionScores(
        hard_requirements_score=ScoreDimension(value=90, explanation=""),
        domain_similarity_score=ScoreDimension(value=80, explanation=""),
        seniority_score=ScoreDimension(value=85, explanation=""),
        technology_score=ScoreDimension(value=70, explanation=""),
        signal_score=ScoreDimension(value=60, explanation=""),
    )
    assert calculate_final_score(scores) == 83


def test_education_deal_breakers_stripped():
    from app.filter.evaluation import sanitize_deal_breakers

    assert sanitize_deal_breakers(["Requires Bachelor's degree"]) == []
    assert sanitize_deal_breakers(["BSc in Computer Science required"]) == []
    assert sanitize_deal_breakers(["BS degree mandatory"]) == []
    assert sanitize_deal_breakers(["Requires active clearance"]) == ["Requires active clearance"]


def test_tenure_only_deal_breakers_stripped():
    from app.filter.evaluation import sanitize_deal_breakers

    assert sanitize_deal_breakers(["5+ years experience"]) == []
    assert sanitize_deal_breakers(["minimum 5 years"]) == []
    assert sanitize_deal_breakers(["5-7 years experience"]) == []
    assert sanitize_deal_breakers(["Missing 5+ years Python experience"]) == ["Missing 5+ years Python experience"]


def test_deal_breakers_force_reject():
    ev = LlmEvaluation(
        extracted=ExtractedRequirements(),
        scores=DimensionScores(
            hard_requirements_score=ScoreDimension(value=95, explanation=""),
            domain_similarity_score=ScoreDimension(value=90, explanation=""),
            seniority_score=ScoreDimension(value=90, explanation=""),
            technology_score=ScoreDimension(value=90, explanation=""),
            signal_score=ScoreDimension(value=90, explanation=""),
        ),
        deal_breakers=["Requires active security clearance not on CV"],
    )
    result = to_pipeline_result(ev, 92, "Company Website")
    assert result["hard_reject_override"] is True
