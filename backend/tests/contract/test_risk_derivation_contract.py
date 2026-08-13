from app.main import app


def test_risk_response_exposes_derivation_chain_schema():
    schemas = app.openapi()["components"]["schemas"]
    response_properties = schemas["RiskResponseData"]["properties"]

    assert "derivation_chains" in response_properties
    assert "DerivationChain" in schemas
    assert "DerivationSignal" in schemas
    assert "DerivationDataRef" in schemas
