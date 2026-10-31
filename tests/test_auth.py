import pytest
from app import create_app
from config import Config
from models import Admin
from extensions import db

def test_admin_login_success(client):
    response = client.post(
        "/login",
        data={"username": "testadmin", "password": "SecretPass123!"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Welcome back" in response.data
    assert b"Dashboard" in response.data

def test_admin_login_failure(client):
    response = client.post(
        "/login",
        data={"username": "testadmin", "password": "WrongPassword!"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Invalid administrator credentials" in response.data

def test_unauthorized_access_redirects(client):
    protected_urls = [
        "/admin/dashboard",
        "/admin/documents",
        "/admin/upload",
        "/admin/qr-manager",
        "/admin/settings",
    ]
    for url in protected_urls:
        response = client.get(url, follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

def test_admin_logout(auth_client):
    response = auth_client.get("/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"You have been signed out" in response.data

    # Protected dashboard should now redirect
    dashboard_res = auth_client.get("/admin/dashboard", follow_redirects=False)
    assert dashboard_res.status_code == 302

def test_cli_create_admin(runner, app):
    result = runner.invoke(
        args=["create-admin", "--username", "cliadmin", "--password", "NewPass987!"]
    )
    assert result.exit_code == 0
    assert "created successfully" in result.output

    with app.app_context():
        admin = Admin.query.filter_by(username="cliadmin").first()
        assert admin is not None
        assert admin.check_password("NewPass987!")

def test_change_password_in_settings(auth_client, app):
    response = auth_client.post(
        "/admin/settings",
        data={
            "current_password": "SecretPass123!",
            "new_password": "BrandNewPassword123!",
            "confirm_password": "BrandNewPassword123!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Administrator password updated successfully" in response.data

    with app.app_context():
        admin = Admin.query.filter_by(username="testadmin").first()
        assert admin.check_password("BrandNewPassword123!")

def test_production_refuses_localhost_or_ip():
    class ProdLocalhostConfig(Config):
        IS_PRODUCTION = True
        PUBLIC_BASE_URL = "http://localhost:5000"

    with pytest.raises(ValueError, match="HTTPS"):
        create_app(ProdLocalhostConfig)

    class ProdHttpDomainConfig(Config):
        IS_PRODUCTION = True
        PUBLIC_BASE_URL = "http://myexample.com"

    with pytest.raises(ValueError, match="HTTPS"):
        create_app(ProdHttpDomainConfig)

    class ProdIpConfig(Config):
        IS_PRODUCTION = True
        PUBLIC_BASE_URL = "https://192.168.1.50"

    with pytest.raises(ValueError, match="IP addresses are not permitted"):
        create_app(ProdIpConfig)

    class ProdValidConfig(Config):
        IS_PRODUCTION = True
        PUBLIC_BASE_URL = "https://qrdocs.mycompany.com"
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    # Valid permanent HTTPS domain starts cleanly
    app = create_app(ProdValidConfig)
    assert app is not None

def test_sub_admin_creation_and_login(auth_client, client, app):
    # Main admin creates a sub-admin
    res = auth_client.post(
        "/admin/users/create",
        data={
            "display_name": "Support Operator",
            "username": "subadmin1",
            "role": "sub_admin",
            "password": "SubAdminPass123!",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"Support Operator" in res.data
    assert b"(sub admin)" in res.data

    with app.app_context():
        sub = Admin.query.filter_by(username="subadmin1").first()
        assert sub is not None
        assert sub.role == "sub_admin"
        assert sub.is_main_admin is False
        assert sub.role_label == "sub admin"
        assert sub.name_display == "Support Operator"
        assert sub.check_password("SubAdminPass123!")

    # Sub-admin logs in successfully
    client.get("/logout")
    login_res = client.post(
        "/login",
        data={"username": "subadmin1", "password": "SubAdminPass123!"},
        follow_redirects=True,
    )
    assert login_res.status_code == 200
    assert b"Support Operator" in login_res.data
    assert b"(sub admin)" in login_res.data

def test_sub_admin_restricted_from_user_management(client, app):
    # Create sub-admin directly in DB
    with app.app_context():
        sub = Admin(username="subworker", display_name="Worker", role="sub_admin")
        sub.set_password("Pass12345!")
        db.session.add(sub)
        db.session.commit()

    # Log in as sub-admin
    client.post(
        "/login",
        data={"username": "subworker", "password": "Pass12345!"},
        follow_redirects=True,
    )

    # Attempt to access user management page
    users_res = client.get("/admin/users", follow_redirects=True)
    assert users_res.status_code == 200
    assert b"Access restricted: Only the Main Admin" in users_res.data

    # Attempt to create an admin
    create_res = client.get("/admin/users/create", follow_redirects=True)
    assert b"Access restricted: Only the Main Admin" in create_res.data

def test_main_admin_delete_sub_admin(auth_client, app):
    # Create a sub-admin
    with app.app_context():
        sub = Admin(username="deleteme", display_name="Temporary User", role="sub_admin")
        sub.set_password("Pass12345!")
        db.session.add(sub)
        db.session.commit()
        sub_id = sub.id

    # Main admin deletes the sub-admin
    del_res = auth_client.post(f"/admin/users/{sub_id}/delete", follow_redirects=True)
    assert del_res.status_code == 200
    assert b"deleted successfully" in del_res.data

    with app.app_context():
        assert db.session.get(Admin, sub_id) is None

def test_main_admin_cannot_delete_self(auth_client, app):
    with app.app_context():
        main = Admin.query.filter_by(username="testadmin").first()
        main_id = main.id

    del_res = auth_client.post(f"/admin/users/{main_id}/delete", follow_redirects=True)
    assert del_res.status_code == 200
    assert b"You cannot delete your own Main Admin account" in del_res.data

    with app.app_context():
        assert db.session.get(Admin, main_id) is not None


