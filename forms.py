from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, DateField, FileField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, EqualTo, Optional

class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign In")

class DocumentUploadForm(FlaskForm):
    title = StringField("Document Title", validators=[DataRequired(), Length(max=255)])
    certificate_code = StringField("Certificate Code / Masked ID (e.g. THX-SEP2626-093, optional)", validators=[Optional(), Length(max=50)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    category = StringField("Category", validators=[Optional(), Length(max=100)])
    tags = StringField("Tags (comma separated)", validators=[Optional(), Length(max=255)])
    author = StringField("Author / Issuer", validators=[Optional(), Length(max=150)])
    document_date = DateField("Document Date", validators=[Optional()], format="%Y-%m-%d")
    expiry_date = DateField("Expiry Date (Informational)", validators=[Optional()], format="%Y-%m-%d")
    file = FileField("Document File (PDF, PNG, JPG)", validators=[DataRequired()])
    submit = SubmitField("Upload Document")

class DocumentEditForm(FlaskForm):
    title = StringField("Document Title", validators=[DataRequired(), Length(max=255)])
    certificate_code = StringField("Certificate Code / Masked ID (e.g. THX-SEP2626-093)", validators=[Optional(), Length(max=50)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    category = StringField("Category", validators=[Optional(), Length(max=100)])
    tags = StringField("Tags (comma separated)", validators=[Optional(), Length(max=255)])
    author = StringField("Author / Issuer", validators=[Optional(), Length(max=150)])
    document_date = DateField("Document Date", validators=[Optional()], format="%Y-%m-%d")
    expiry_date = DateField("Expiry Date (Informational)", validators=[Optional()], format="%Y-%m-%d")
    submit = SubmitField("Update Metadata")

class DocumentReplaceFileForm(FlaskForm):
    file = FileField("Select Replacement File", validators=[DataRequired()])
    submit = SubmitField("Replace File")

class ChangePasswordForm(FlaskForm):
    display_name = StringField("Custom Display Name", validators=[Optional(), Length(max=100)])
    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField("New Password", validators=[
        DataRequired(),
        Length(min=8, message="Password must be at least 8 characters long.")
    ])
    confirm_password = PasswordField("Confirm New Password", validators=[
        DataRequired(),
        EqualTo("new_password", message="Passwords must match.")
    ])
    submit = SubmitField("Save Settings")

class SubAdminCreateForm(FlaskForm):
    display_name = StringField("Custom Name", validators=[DataRequired(), Length(min=2, max=100)])
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    role = SelectField("Account Role", choices=[("sub_admin", "Sub Admin"), ("admin", "Main Admin")], default="sub_admin")
    password = PasswordField("Password", validators=[
        DataRequired(),
        Length(min=6, message="Password must be at least 6 characters long.")
    ])
    submit = SubmitField("Create Admin Account")

class SubAdminEditForm(FlaskForm):
    display_name = StringField("Custom Name", validators=[DataRequired(), Length(min=2, max=100)])
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    role = SelectField("Account Role", choices=[("sub_admin", "Sub Admin"), ("admin", "Main Admin")])
    new_password = PasswordField("New Password (leave empty to keep current password)", validators=[
        Optional(),
        Length(min=6, message="Password must be at least 6 characters long.")
    ])
    submit = SubmitField("Update Account")

class EmptyForm(FlaskForm):
    """Empty form used to validate CSRF tokens for POST actions (delete, deactivate, etc.)"""
    pass

