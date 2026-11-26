def test_map_page_is_served(client) -> None:
    response = client.get("/map")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    html = response.text
    assert 'id="map"' in html
    assert "leaflet@1.9.4" in html
    assert "/static/map.js" in html


def test_map_assets_are_served(client) -> None:
    js = client.get("/static/map.js")
    css = client.get("/static/map.css")

    assert js.status_code == css.status_code == 200
    assert "/api/stations" in js.text
    assert "OpenStreetMap" in js.text


def test_map_page_is_not_part_of_the_json_api(client) -> None:
    spec = client.get("/openapi.json").json()

    assert spec["paths"]["/map"]["get"]["tags"] == ["pages"]
