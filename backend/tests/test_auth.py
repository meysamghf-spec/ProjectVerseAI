"""User accounts: hashing, sessions, roles, CSRF, bootstrap, isolation, and limits."""

from app.auth import hash_password, verify_password

CSRF = {"X-Requested-With": "XMLHttpRequest"}


def _login(client, email="admin@example.com", password="admin-password-123"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password}, headers=CSRF)


def test_login_requires_csrf_header(accounts_client):
    response = accounts_client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password-123"}
    )
    assert response.status_code == 403
    assert "set-cookie" not in response.headers


def test_password_hashing_is_salted_and_verifiable():
    first = hash_password("correct horse battery")
    second = hash_password("correct horse battery")
    assert first != second
    assert first.startswith("scrypt$")
    assert "correct horse" not in first
    assert verify_password(first, "correct horse battery")
    assert not verify_password(first, "wrong password!!")
    assert not verify_password("garbage", "x")


def test_bootstrap_admin_login_me_and_logout(accounts_client):
    client = accounts_client
    assert client.get("/api/v1/auth/me").json()["authenticated"] is False
    assert client.get("/api/v1/projects").status_code == 401
    response = _login(client)  # email is case-insensitive; bootstrap used Admin@Example.com
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"
    cookie = response.headers["set-cookie"]
    assert "pv_session=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    me = client.get("/api/v1/auth/me").json()
    assert me["authenticated"] is True and me["user"]["email"] == "admin@example.com"
    assert "password_hash" not in me["user"]
    assert client.get("/api/v1/projects").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/projects").status_code == 401


def test_wrong_password_and_rate_limit(accounts_client):
    client = accounts_client
    for _ in range(3):
        assert _login(client, password="not-the-password").status_code == 401
    assert _login(client).status_code == 429


def test_cookie_writes_need_the_csrf_header(accounts_client):
    client = accounts_client
    _login(client)
    body = {"prompt": "Build a small web app in 3 months", "name": "App", "generate": False}
    assert client.post("/api/v1/projects", json=body).status_code == 403
    assert client.post("/api/v1/projects", json=body, headers=CSRF).status_code == 201


def test_admin_creates_users_and_projects_are_isolated(accounts_client):
    client = accounts_client
    _login(client)
    created = client.post(
        "/api/v1/admin/users",
        json={"email": "user@example.com", "password": "user-password-123", "role": "user"},
        headers=CSRF,
    )
    assert created.status_code == 201
    user_id = created.json()["user"]["id"]
    duplicate = client.post(
        "/api/v1/admin/users",
        json={"email": "USER@example.com", "password": "user-password-123"},
        headers=CSRF,
    )
    assert duplicate.status_code == 409
    weak = client.post("/api/v1/admin/users", json={"email": "w@example.com", "password": "short"}, headers=CSRF)
    assert weak.status_code == 422
    admin_project = client.post(
        "/api/v1/projects", json={"prompt": "Admin project for 2 months", "name": "Admin only"}, headers=CSRF
    ).json()

    client.post("/api/v1/auth/logout")
    assert _login(client, "user@example.com", "user-password-123").status_code == 200
    assert client.get("/api/v1/projects").json()["total"] == 0
    assert client.get(f"/api/v1/projects/{admin_project['id']}").status_code == 404
    assert client.get("/api/v1/admin/users").status_code == 403

    client.post("/api/v1/auth/logout")
    _login(client)
    disabled = client.patch(f"/api/v1/admin/users/{user_id}", json={"is_active": False}, headers=CSRF)
    assert disabled.status_code == 200 and disabled.json()["user"]["is_active"] is False
    client.post("/api/v1/auth/logout")
    assert _login(client, "user@example.com", "user-password-123").status_code == 401


def test_last_admin_cannot_be_demoted_and_password_change(accounts_client):
    client = accounts_client
    me = _login(client).json()["user"]
    demote = client.patch(f"/api/v1/admin/users/{me['id']}", json={"role": "user"}, headers=CSRF)
    assert demote.status_code == 409
    wrong = client.post(
        "/api/v1/auth/password",
        json={"current_password": "nope-nope-nope", "new_password": "another-password-1"},
        headers=CSRF,
    )
    assert wrong.status_code == 400
    changed = client.post(
        "/api/v1/auth/password",
        json={"current_password": "admin-password-123", "new_password": "another-password-1"},
        headers=CSRF,
    )
    assert changed.status_code == 204
    client.post("/api/v1/auth/logout")
    assert _login(client).status_code == 401
    assert _login(client, password="another-password-1").status_code == 200


def test_bearer_token_header_works_for_scripts(accounts_client):
    client = accounts_client
    response = _login(client)
    token = response.cookies.get("pv_session")
    client.cookies.clear()
    assert client.get("/api/v1/projects").status_code == 401
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/projects", headers=headers).status_code == 200
    # Bearer requests are not cookie-based, so no CSRF header is required.
    made = client.post("/api/v1/projects", json={"prompt": "Script project 2 months"}, headers=headers)
    assert made.status_code == 201


def test_root_health(accounts_client):
    response = accounts_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
