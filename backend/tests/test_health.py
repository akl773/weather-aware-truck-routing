from django.test import Client, override_settings


@override_settings(GIT_SHA="abc1234")
def test_health_reports_status_and_build_version():
    response = Client().get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "abc1234"}


def test_openapi_schema_documents_the_health_endpoint():
    response = Client().get("/api/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json")

    assert response.status_code == 200
    assert "/api/health" in response.json()["paths"]
