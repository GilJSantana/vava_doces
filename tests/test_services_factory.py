from src.application.services_factory import build_analysis_services


def test_build_analysis_services_returns_none_without_adapter():
    service, product_service = build_analysis_services(None, lambda _: object())

    assert service is None
    assert product_service is None


def test_build_analysis_services_uses_product_service_factory():
    calls = []

    def fake_product_factory(adapter):
        calls.append(adapter)
        return "product_service"

    service, product_service = build_analysis_services("adapter", fake_product_factory)

    assert service is not None
    assert product_service == "product_service"
    assert calls == ["adapter"]

