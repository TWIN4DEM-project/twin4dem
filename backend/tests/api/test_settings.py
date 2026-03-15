def test_list_success(admin_client):
    response = admin_client.get("/api/v1/settings/")

    assert response.status_code == 200
    assert response.json() == [
        {
            "courtSize": 5,
            "governmentConnectivityDegree": 3,
            "governmentSize": 6,
            "id": 1,
            "label": "test_admin settings",
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
        "abstentionThreshold": 0.1,
        "courtSize": 5,
        "courtProbabilityFor": 0.5,
        "dataUpdateFrequency": 10,
        "governmentConnectivityDegree": 3,
        "governmentSize": 6,
        "governmentProbabilityFor": 0.7,
        "parliamentMajorityProbabilityFor": 0.5,
        "parliamentOppositionProbabilityFor": 0.5,
        "id": 1,
        "label": "test_admin settings",
        "legislativePathProbability": 0.7,
        "officeRetentionSensitivity": 5.0,
        "parliamentSize": 100,
        "parties": [
            {"id": 1, "label": "majority", "memberCount": 51, "position": "majority"},
            {
                "id": 2,
                "label": "opposition",
                "memberCount": 49,
                "position": "opposition",
            },
        ],
        "socialInfluenceSusceptibility": 0.5,
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
