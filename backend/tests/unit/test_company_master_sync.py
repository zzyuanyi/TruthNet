from app.application.services.company_master_sync import (
    plan_missing_companies,
    wind_code_for_current_a_share,
)
from app.application.services.industry_fill.universe import (
    build_current_universe_snapshot,
)


def test_exchange_mapping_for_current_a_shares():
    assert wind_code_for_current_a_share("600000") == "600000.SH"
    assert wind_code_for_current_a_share("001232") == "001232.SZ"
    assert wind_code_for_current_a_share("920038") == "920038.BJ"


def test_plan_only_missing_companies_with_auditable_identity():
    snapshot = build_current_universe_snapshot(
        [("600000", "浦发银行"), ("920038", "森合高科")],
        provider_version="test",
        retrieved_at="2026-08-23T00:00:00+00:00",
        min_size=1,
    )
    rows = plan_missing_companies({"600000.SH"}, snapshot)
    assert len(rows) == 1
    assert rows[0].wind_code == "920038.BJ"
    assert rows[0].sec_name == "森合高科"
    assert rows[0].exchange_code == "BJ"
    assert rows[0].entity_id == "company_920038_BJ"
