def test_list_success(admin_client):
    response = admin_client.get("/api/v1/settings/")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "courtSize": 5,
            "governmentConnectivityDegree": 3,
            "governmentSize": 15,
            "label": "default",
            "parliamentSize": 100,
        }
    ]


def test_list_anonymous_forbidden(client):
    response = client.get("/api/v1/settings/")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


def test_get_by_id_success(admin_client):
    response = admin_client.get("/api/v1/settings/1/")

    assert response.status_code == 200
    assert response.json() == {
        "abstentionThreshold": 0.2,
        "courtSize": 5,
        "dataUpdateFrequency": 10,
        "governmentConnectivityDegree": 3,
        "governmentSize": 15,
        "governmentProbabilityFor": 0.5,
        "id": 1,
        "label": "default",
        "legislativePathProbability": 0.5,
        "parliamentSize": 100,
        "parties": [
            {"id": 1, "label": "Party A", "memberCount": 25, "position": "majority"},
            {"id": 2, "label": "Party B", "memberCount": 35, "position": "majority"},
            {"id": 3, "label": "Party C", "memberCount": 40, "position": "opposition"},
        ],
        "userId": 1,
    }


def test_get_by_id_404(admin_client):
    response = admin_client.get("/api/v1/settings/0/")

    assert response.status_code == 404


def test_get_by_id_anonymous_forbidden(client):
    response = client.get("/api/v1/settings/1/")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }
