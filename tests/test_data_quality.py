from scripts.run_quality_checks import CheckResult, render_report, status_from_count


def test_status_from_count() -> None:
    assert status_from_count(0) == "PASS"
    assert status_from_count(3) == "FAIL"


def test_render_report_contains_summary() -> None:
    report = render_report(
        [
            CheckResult("DQ001", "主键重复检查", "table_a", "PASS", 0, "ok"),
            CheckResult("DQ002", "关键字段为空检查", "table_b", "FAIL", 2, "bad"),
        ]
    )
    assert "检查项总数：2" in report
    assert "| DQ002 | 关键字段为空检查 | `table_b` | FAIL | 2 | bad |" in report

