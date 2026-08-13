from scripts.run_quality_checks import CheckResult, has_failures, render_report, status_from_count


def test_status_from_count() -> None:
    assert status_from_count(0) == "PASS"
    assert status_from_count(3) == "FAIL"


def test_has_failures_detects_quality_gate_state() -> None:
    passing = [CheckResult("DQ001", "rule", "table_a", "PASS", 0, "ok")]
    failing = passing + [CheckResult("DQ002", "rule", "table_b", "FAIL", 2, "bad")]

    assert has_failures(passing) is False
    assert has_failures(failing) is True


def test_render_report_contains_summary() -> None:
    report = render_report(
        [
            CheckResult("DQ001", "主键重复检查", "table_a", "PASS", 0, "ok"),
            CheckResult("DQ002", "关键字段为空检查", "table_b", "FAIL", 2, "bad"),
        ]
    )
    assert "检查项总数：2" in report
    assert "| DQ002 | 关键字段为空检查 | `table_b` | FAIL | 2 | bad |" in report
