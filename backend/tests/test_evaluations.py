from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.evaluations import EvaluationService


@pytest.mark.asyncio
async def test_evaluation_cases_are_seeded(db_session: AsyncSession) -> None:
    service = EvaluationService(db_session)

    cases = await service.list_cases()

    assert len(cases) == 10
    assert sum(1 for evaluation_case in cases if evaluation_case.case_set == "required") == 5
    assert {evaluation_case.slug for evaluation_case in cases} >= {"re-sale", "nobu-milan", "pizzeria-da-michele"}


@pytest.mark.asyncio
async def test_evaluation_runner_scores_required_cases(db_session: AsyncSession) -> None:
    service = EvaluationService(db_session)

    run = await service.run(case_set="required")

    assert run.case_count == 5
    assert run.averages["validity"] == 1.0
    assert run.averages["category_coverage"] is not None
    assert run.averages["price_coverage"] is not None
    assert any(metric.slug == "pizzeria-da-michele" and metric.price_coverage < 1 for metric in run.cases)


@pytest.mark.asyncio
async def test_evaluation_api_lists_cases_and_runs_full_set(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cases_response = await client.get("/api/evaluations/cases")
        run_response = await client.post("/api/evaluations/run", json={"case_set": "full"})

    assert cases_response.status_code == 200
    assert len(cases_response.json()) == 10
    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["case_count"] == 10
    assert payload["averages"]["validity"] == 1.0


@pytest.mark.asyncio
async def test_evaluation_api_returns_stored_run(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_response = await client.post("/api/evaluations/run", json={"case_set": "required"})
        run_id = run_response.json()["id"]
        stored_response = await client.get(f"/api/evaluations/{run_id}")

    assert stored_response.status_code == 200
    assert stored_response.json()["id"] == run_id
    assert stored_response.json()["case_count"] == 5
