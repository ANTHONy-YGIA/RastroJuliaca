from conftest import PASSWORD, Actor, register


def test_registro_y_sesion():
    a = register("ciudadano@prueba.test", "DENUNCIANTE")
    me = a.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["role"] == "DENUNCIANTE"
    assert me.json()["user"]["alias"].startswith("COL-")
    # La cookie de sesión es HttpOnly y SameSite=Strict
    set_cookie = a.client.post("/api/auth/login", json={"email": "ciudadano@prueba.test", "password": PASSWORD}).headers.get_list("set-cookie")
    session_cookie = next(c for c in set_cookie if c.startswith("rj_session="))
    assert "HttpOnly" in session_cookie and "samesite=strict" in session_cookie.lower()


def test_registro_rechaza_duplicado_y_password_debil():
    register("dup@prueba.test")
    a = Actor()
    r = a.client.post("/api/auth/register", json={"email": "dup@prueba.test", "full_name": "Otra", "password": PASSWORD, "role": "DENUNCIANTE", "accept_terms": True})
    assert r.status_code == 409
    r = a.client.post("/api/auth/register", json={"email": "debil@prueba.test", "full_name": "Débil", "password": "soloLetrasAqui", "role": "DENUNCIANTE", "accept_terms": True})
    assert r.status_code == 422
    r = a.client.post("/api/auth/register", json={"email": "terms@prueba.test", "full_name": "Sin términos", "password": PASSWORD, "role": "DENUNCIANTE", "accept_terms": False})
    assert r.status_code == 422


def test_no_se_puede_autoregistrar_personal():
    a = Actor()
    for role in ("REVISOR", "ADMIN"):
        r = a.client.post("/api/auth/register", json={"email": f"{role}@prueba.test", "full_name": "Intruso", "password": PASSWORD, "role": role, "accept_terms": True})
        assert r.status_code == 422


def test_login_credenciales_invalidas_y_bloqueo():
    register("bloqueo@prueba.test")
    a = Actor()
    for _ in range(5):
        assert a.client.post("/api/auth/login", json={"email": "bloqueo@prueba.test", "password": "Incorrecta-123"}).status_code == 401
    r = a.client.post("/api/auth/login", json={"email": "bloqueo@prueba.test", "password": PASSWORD})
    assert r.status_code == 423  # bloqueo temporal tras intentos fallidos
    assert a.client.post("/api/auth/login", json={"email": "noexiste@prueba.test", "password": PASSWORD}).status_code == 401


def test_endpoints_requieren_autenticacion():
    a = Actor()
    assert a.get("/api/auth/me").status_code == 401
    assert a.get("/api/cases/mine").status_code == 401
    assert a.get("/api/review/dashboard").status_code == 401
    assert a.get("/api/admin/overview").status_code == 401


def test_csrf_obligatorio_en_operaciones_de_escritura():
    a = register("csrf@prueba.test")
    r = a.client.post("/api/me/notifications/read-all")  # sin cabecera CSRF
    assert r.status_code == 403
    r = a.client.post("/api/me/notifications/read-all", headers={"X-CSRF-Token": "falso"})
    assert r.status_code == 403
    assert a.post("/api/me/notifications/read-all").status_code == 200


def test_logout_invalida_sesion():
    a = register("salir@prueba.test")
    assert a.post("/api/auth/logout").status_code == 200
    assert a.get("/api/auth/me").status_code == 401


def test_rate_limit_login(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_login", 3)
    a = Actor()
    codes = [a.client.post("/api/auth/login", json={"email": "x@prueba.test", "password": "Incorrecta-123"}).status_code for _ in range(4)]
    assert codes[-1] == 429


def test_cabeceras_de_seguridad():
    r = Actor().get("/api/health")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
