def safe_divide(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def rfm_segment(r_score: int, f_score: int, m_score: int) -> str:
    if r_score >= 4 and f_score >= 4 and m_score >= 4:
        return "高价值用户"
    if r_score >= 4 and f_score >= 3:
        return "潜力用户"
    if r_score <= 2:
        return "流失风险用户"
    return "一般用户"


def test_conversion_rate_formula() -> None:
    assert safe_divide(80, 100) == 0.8
    assert safe_divide(1, 0) == 0.0


def test_rfm_segment_rules() -> None:
    assert rfm_segment(5, 5, 5) == "高价值用户"
    assert rfm_segment(4, 3, 2) == "潜力用户"
    assert rfm_segment(1, 5, 5) == "流失风险用户"
    assert rfm_segment(3, 2, 2) == "一般用户"

