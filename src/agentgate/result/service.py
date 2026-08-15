from agentgate.contracts import GateDecision, Result, Verdict


def aggregate_results(results: list[Result], threshold: float = 0.95) -> GateDecision:
    passed = sum(item.verdict == Verdict.PASS for item in results)
    failed = sum(item.verdict == Verdict.FAIL for item in results)
    review = sum(item.verdict == Verdict.REVIEW for item in results)
    score = sum(item.score for item in results) / len(results) if results else 0.0
    verdict = Verdict.PASS if results and not review and score >= threshold else Verdict.FAIL
    return GateDecision(verdict=verdict, passed=passed, failed=failed, review=review,
                        score=score, threshold=threshold,
                        reason="达到发布门槛" if verdict == Verdict.PASS else "未达到发布门槛")
