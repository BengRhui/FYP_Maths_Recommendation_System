"""
This file handles all forms involved in the system:
- Student and teacher registration
- Login
- User Profile
- Password Reset and Change
"""

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import forms as auth_forms

# Retrieve the current user
User = get_user_model()

# A constant stating the error message for existing emails
EMAIL_ERROR_MESSAGES = {"unique": "User with this email address already exists."}

# The class and function to attach the CSS label for different forms
class _BootstrapMixin:
    def _style(self):

        # Loop through the fields in the form
        for field in self.fields.values():

            # Retrieve the widget (the object that renders HTML) and CSS label
            widget = field.widget
            css = "form-control form-control-lg"

            # Attach "form_check-input" for check box
            if isinstance(widget, forms.CheckboxInput):
                css = "form-check-input"

            # Attach normally for other forms
            widget.attrs.setdefault("class", css)


# The class that handles the student registration form
class StudentRegistrationForm(_BootstrapMixin, auth_forms.UserCreationForm):

    # Additional full name field
    full_name = forms.CharField(label="Full name", max_length=150)

    # Class to configure the fields (from User) shown in the form
    class Meta:
        model = User
        fields = ["full_name", "email"]
        error_messages = {"email": EMAIL_ERROR_MESSAGES}

    # A function to set up the field labels, placeholders, and styling for the form
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Password"
        self.fields["password2"].label = "Confirm password"
        self.fields["full_name"].widget.attrs.setdefault("autofocus", True)
        self.fields["full_name"].widget.attrs.setdefault("placeholder", "Jane Doe")
        self.fields["email"].widget.attrs.setdefault("placeholder", "jane.doe@example.com")
        self.fields["password1"].widget.attrs.setdefault("placeholder", "Create a password")
        self.fields["password2"].widget.attrs.setdefault("placeholder", "Re-enter your password")
        self._style()

    # A function to convert the form into a student user
    def save(self, commit=True):

        # Create the student object first and set its full name and role
        user = super().save(commit=False)
        user.role = User.Role.STUDENT
        user.full_name = self.cleaned_data["full_name"]

        # Only write to the database when required
        if commit:
            user.save()

        # And return the generated user
        return user


# The class to handle teacher registration form
class TeacherRegistrationForm(_BootstrapMixin, auth_forms.UserCreationForm):

    # Two additional fields added: Full name and registration code
    full_name = forms.CharField(label="Full name", max_length=150)
    registration_code = forms.CharField(
        label="Teacher registration code",
        help_text="This code protects student privacy by ensuring only "
        "verified teachers can view joined students.",
    )

    # The class to configure the fields (from User) shown in the form
    class Meta:
        model = User
        fields = ["full_name", "email"]
        error_messages = {"email": EMAIL_ERROR_MESSAGES}

    # A function to set up the field labels, placeholders, and styling for the form
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Password"
        self.fields["password2"].label = "Confirm password"
        self.fields["full_name"].widget.attrs.setdefault("autofocus", True)
        self.fields["full_name"].widget.attrs.setdefault("placeholder", "Jane Doe")
        self.fields["email"].widget.attrs.setdefault("placeholder", "jane.doe@example.com")
        self.fields["password1"].widget.attrs.setdefault("placeholder", "Create a password")
        self.fields["password2"].widget.attrs.setdefault("placeholder", "Re-enter your password")
        self.fields["registration_code"].widget.attrs.setdefault(
            "placeholder", "Enter your unique access code"
        )
        self._style()

    # A function to validate the input registration code (should match with .env)
    def clean_registration_code(self):

        # Extract the inputted code
        code = self.cleaned_data["registration_code"].strip()

        # Raise error if the code is invalid
        if code != settings.TEACHER_REGISTRATION_CODE:
            raise forms.ValidationError(
                "That teacher registration code is not valid."
            )

        # Return the code if it is valid
        return code

    # A function to convert the form into a teacher user
    def save(self, commit=True):

        # First, create the user object
        user = super().save(commit=False)
        user.role = User.Role.TEACHER
        user.full_name = self.cleaned_data["full_name"]

        # Only save to database when required
        if commit:
            user.save()

        # Return the teacher object
        return user


# A class to handle the login form
class EmailLoginForm(_BootstrapMixin, auth_forms.AuthenticationForm):

    # Additional email address field
    username = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"autofocus": True, "placeholder": "name@institution.edu"}),
    )

    # A function to set up field placeholders and styling for the login form
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password"].widget.attrs.setdefault("placeholder", "Enter your password")
        self._style()


# A class to handle the user profile form (after students and teachers login)
class ProfileForm(_BootstrapMixin, forms.ModelForm):

    # Define the fields from User to be displayed
    class Meta:
        model = User
        fields = ["full_name", "email"]
        error_messages = {"email": EMAIL_ERROR_MESSAGES}

    # A function to set up styling for the profile form
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


# A class to handle the password reset form (sending email)
class PasswordResetForm(_BootstrapMixin, auth_forms.PasswordResetForm):

    # An additional field not in Django default settings
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={"autofocus": True, "placeholder": "scholar@university.edu"}),
    )

    # A function to set up styling for the password reset form
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


# A class to handle the forget password form (setting password)
class SetPasswordForm(_BootstrapMixin, auth_forms.SetPasswordForm):

    # A function to set up field labels, placeholders, and styling for the set password form
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "New password"
        self.fields["new_password2"].label = "Confirm new password"
        self.fields["new_password1"].widget.attrs.setdefault("placeholder", "Create a new password")
        self.fields["new_password2"].widget.attrs.setdefault("placeholder", "Re-enter your new password")
        self._style()


# A class to handle the change password form (after users login)
class PasswordChangeForm(_BootstrapMixin, auth_forms.PasswordChangeForm):

    # A function to set up field labels, placeholders, and styling for the password change form
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Current password"
        self.fields["new_password1"].label = "New password"
        self.fields["new_password2"].label = "Confirm new password"
        self.fields["new_password1"].help_text = ""
        self.fields["old_password"].widget.attrs.setdefault("placeholder", "Enter your current password")
        self.fields["new_password1"].widget.attrs.setdefault("placeholder", "Create a new password")
        self.fields["new_password2"].widget.attrs.setdefault("placeholder", "Re-enter your new password")
        self._style()
