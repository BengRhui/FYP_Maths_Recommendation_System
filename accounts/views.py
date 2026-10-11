"""
This file translates the functions in urls.py into views to render HTML pages.
"""

from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from .forms import (
    EmailLoginForm,
    PasswordChangeForm,
    PasswordResetForm,
    ProfileForm,
    SetPasswordForm,
    StudentRegistrationForm,
    TeacherRegistrationForm,
)

# The key to help re-insert the cached values inputted into forms
_FLASHED_FORM_ERRORS_SESSION_KEY = "flashed_form_errors"


# A function to store the data inside a form when error happens
def _flash_form_errors(request, form, keep_fields):

    # Store data under the session key
    request.session[_FLASHED_FORM_ERRORS_SESSION_KEY] = {
        "path": request.path,
        "errors": form.errors.get_json_data(),
        "data": {name: form.data.get(name, "") for name in keep_fields},
    }


# A function to rebuild the form and re-insert the cached data when error occurs
def _restore_flashed_form(request, form_class):

    # Retrieve data from the session key
    flashed = request.session.get(_FLASHED_FORM_ERRORS_SESSION_KEY)

    # Return an empty form if no data is cached
    if not flashed or flashed.get("path") != request.path:
        return form_class()

    # Remove the stored cached values
    del request.session[_FLASHED_FORM_ERRORS_SESSION_KEY]

    # Build the form with the cached data
    form = form_class(initial=flashed["data"])

    # Apply the error message to the form
    form.cleaned_data = {}
    for field, field_errors in flashed["errors"].items():
        target = None if field == "__all__" else field
        for error in field_errors:
            form.add_error(target, error["message"])

    # Lastly return the form
    return form


# A class to handle the login page
class LoginView(auth_views.LoginView):

    # Components of the login page
    template_name = "account/login.html"
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True

    # A function to render the login form
    def get(self, request, *args, **kwargs):

        # If any errors happen previously, restore the cached data
        flashed = request.session.get(_FLASHED_FORM_ERRORS_SESSION_KEY)
        if flashed and flashed.get("path") == request.path:
            self.extra_context = {"form": _restore_flashed_form(request, self.authentication_form)}

        # Return the login page
        return super().get(request, *args, **kwargs)

    # A function to flash errors and redirect users back to the login page
    def form_invalid(self, form):
        _flash_form_errors(self.request, form, keep_fields=["username"])
        return redirect("accounts:login")


# A class to navigate users to landing page after logout
class LogoutView(auth_views.LogoutView):

    # Redirect to the landing page
    next_page = reverse_lazy("landing")
    http_method_names = ["get", "post", "options"]

    # A function to redirect plain GET requests to the landing page
    def get(self, request, *args, **kwargs):
        return redirect("landing")


# A class to handle the password reset page
class PasswordResetView(auth_views.PasswordResetView):

    # Components of a password reset page
    template_name = "account/password_reset.html"
    email_template_name = "account/password_reset_email.txt"
    subject_template_name = "account/password_reset_subject.txt"
    form_class = PasswordResetForm
    success_url = reverse_lazy("accounts:password_reset_done")

    # A function to render the password reset form
    def get(self, request, *args, **kwargs):

        # Restore the cached data if errors happen
        flashed = request.session.get(_FLASHED_FORM_ERRORS_SESSION_KEY)
        if flashed and flashed.get("path") == request.path:
            self.extra_context = {"form": _restore_flashed_form(request, self.form_class)}

        # Render the password reset page
        return super().get(request, *args, **kwargs)

    # A function to display errors and redirect back to the password reset page (POST requests)
    def form_invalid(self, form):
        _flash_form_errors(self.request, form, keep_fields=["email"])
        return redirect("accounts:password_reset")


# A class to handle the password reset page after submitting email
class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "account/password_reset_done.html"


# A class to handle the password reset page from the email link
class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "account/password_reset_confirm.html"
    form_class = SetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")


# A class to handle the password reset page after password is resetted
class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "account/password_reset_complete.html"


# A function to redirect users to registration page (where they select student or teachers)
def register_choice(request):

    # For authenticated users, they shall not be redirected to this page, so navigate to their landing pages
    if request.user.is_authenticated:

        # Redirect teachers to teacher dashboard
        if request.user.is_teacher:
            return redirect("classes:teacher_dashboard")

        # Redirect students to student dashboard
        return redirect("learning:dashboard")

    # If not authenticated, then land on the registration choice page
    return render(request, "account/register_choice.html")


# A function to handle student registration
def register_student(request):

    # For students who logged in, they are redirected to their main dashboard
    if request.user.is_authenticated:
        return redirect("learning:dashboard")

    # If the form is submitted
    if request.method == "POST":
        form = StudentRegistrationForm(request.POST)

        # If the details filled in are valid
        if form.is_valid():

            # Create the user and land them to the diagnostic page
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome to AdeptMath! Your account is ready.")
            return redirect("learning:diagnostic_intro")

        # Show errors if details are invalid
        _flash_form_errors(request, form, keep_fields=["full_name", "email"])
        return redirect("accounts:register_student")

    # For GET requests, restore the cached data and render the HTML file
    form = _restore_flashed_form(request, StudentRegistrationForm)
    return render(request, "account/register_student.html", {"form": form})


# A function to handle teacher registration
def register_teacher(request):

    # For teachers who are already logged in, they are redirected to their dashboard
    if request.user.is_authenticated:
        return redirect("learning:dashboard")

    # If a form is submitted
    if request.method == "POST":
        form = TeacherRegistrationForm(request.POST)

        # If details are correct, navigate to the main dashboard
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Your teacher account is ready.")
            return redirect("classes:teacher_dashboard")

        # If details contain error, show the error message
        _flash_form_errors(request, form, keep_fields=["full_name", "email", "registration_code"])
        return redirect("accounts:register_teacher")

    # For GET requests, restore cached data and render the HTML page
    form = _restore_flashed_form(request, TeacherRegistrationForm)
    return render(request, "account/register_teacher.html", {"form": form})


# A function to handle student and teacher profile page
@login_required
def profile(request):

    # The components of the profile page
    password_form = PasswordChangeForm(user=request.user)

    # Check if the request is submitted by the page or JavaScript
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # If the request is a change password request
    if request.method == "POST" and request.POST.get("action") == "change_password":

        # Extract the password form
        password_form = PasswordChangeForm(user=request.user, data=request.POST)

        # Check if the password is valid
        if password_form.is_valid():

            # Update the user password to DB
            user = password_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Your password has been changed.")

            # If the request is from JavaScript, just have to send a simple JSON response
            if is_ajax:
                return JsonResponse({"success": True})

            # If not, redirect back to the profile page
            return redirect("accounts:profile")

        # If password is not valid, and if it is a JavaScript request
        if is_ajax:

            # Return the current details in JSON format
            html = render_to_string(
                "account/_password_form.html", {"password_form": password_form}, request=request
            )
            return JsonResponse({"success": False, "html": html})

        # If it's not a JavaScript request, just refresh the profile page
        form = ProfileForm(instance=request.user)

    # If it is a profile edit request
    elif request.method == "POST":

        # Extract details from the form and upload changed details to database
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:profile")

    # GET request: Load the profile page
    else:
        form = ProfileForm(instance=request.user)

    # Combine details of both scenarios into one dict
    context = {"form": form, "password_form": password_form}

    # If the profile page is student page
    if request.user.is_student:

        # Render the class card
        context["memberships"] = list(
            request.user.class_memberships.filter(is_active=True)
            .select_related("school_class", "school_class__teacher")
            .order_by("joined_at")
        )

    # Return the profile page
    return render(request, "account/profile.html", context)
