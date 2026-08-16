from agentgate.contracts import GateDecision, Result, Verdict


METRIC_GROUPS = (
    ("tool_accuracy", "工具准确率", {"required-tool", "forbidden-tool", "tool-arguments"}),
    ("state_accuracy", "状态准确率", {"final-state"}),
    ("policy_compliance", "策略合规率", {"policy-compliance"}),
)


def calculate_metrics(results: list[Result]) -> list[dict]:
    metrics = []
    for key, label, evaluator_ids in METRIC_GROUPS:
        selected = [item for item in results if item.evaluator_id in evaluator_ids]
        if not selected:
            continue
        passed = sum(item.verdict == Verdict.PASS for item in selected)
        metrics.append({"key": key, "label": label, "score": passed / len(selected),
                        "passed": passed, "total": len(selected)})
    passed = sum(item.verdict == Verdict.PASS for item in results)
    metrics.insert(0, {"key": "overall_score", "label": "综合得分",
                       "score": sum(item.score for item in results) / len(results) if results else 0.0,
                       "passed": passed, "total": len(results)})
    return metrics


def aggregate_results(results: list[Result], threshold: float = 0.95) -> GateDecision:
    passed = sum(item.verdict == Verdict.PASS for item in results)
    failed = sum(item.verdict == Verdict.FAIL for item in results)
    review = sum(item.verdict == Verdict.REVIEW for item in results)
    score = sum(item.score for item in results) / len(results) if results else 0.0
    verdict = Verdict.PASS if results and not review and score >= threshold else Verdict.FAIL
    return GateDecision(verdict=verdict, passed=passed, failed=failed, review=review,
                        score=score, threshold=threshold,
                        reason="达到发布门槛" if verdict == Verdict.PASS else "未达到发布门槛")
