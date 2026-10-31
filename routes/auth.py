from urllib.parse import urlparse
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from extensions import limiter, db
from models import Admin
from forms import LoginForm

auth_bp = Blueprint("auth", __name__)

def is_safe_url(target: str) -> bool:
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)
    # Target must be relative path on same host
    return test_url.scheme in ("", ref_url.scheme) and test_url.netloc in ("", ref_url.netloc) and not target.startswith("//") and not target.startswith("\\\\")

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data

        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            login_user(admin, remember=True)
            flash("Welcome back! You have successfully signed in.", "success")
            
            next_page = request.args.get("next")
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for("admin.dashboard"))
        else:
            flash("Invalid administrator credentials. Please check username and password.", "danger")

    return render_template("auth/login.html", form=form)

@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))

