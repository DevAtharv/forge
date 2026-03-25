from forge.agents.aggregator import PipelineAggregator
from forge.schemas import AgentResult, Artifact, OrchestrationPlan, StageExecution, StagePlan


def test_aggregator_attaches_document_for_code_artifacts() -> None:
    aggregator = PipelineAggregator()
    plan = OrchestrationPlan(
        intent="Build code",
        response_format="code",
        context_policy="recent_plus_profile",
        stages=[StagePlan(name="implement", agents=["code"], tasks={"code": "Build"})],
    )
    stage = StageExecution(
        name="implement",
        outputs={
            "code": AgentResult(
                agent="code",
                summary="Done",
                user_visible_text="Implemented the requested API.",
                artifacts=[
                    Artifact(
                        name="app.py",
                        language="python",
                        content="print('hello')\n" * 300,
                    )
                ],
            )
        },
    )

    payload = aggregator.format(plan, [stage])

    assert payload.document_name == "forge-response.md"
    assert payload.document_bytes is not None
    assert "Full output is attached as a document." in payload.text
