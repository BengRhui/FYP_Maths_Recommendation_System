"""
This file restricts the access of students to the system until they complete the diagnostic.
"""

from django.shortcuts import redirect

from .models import StudentProfile


# The routes that the students can access: diagnostic and authentication
EXEMPT_ROUTES = frozenset(
    {
        "learning:diagnostic_intro",
        "learning:diagnostic_start",
        "learning:diagnostic_question",
        "learning:diagnostic_results",
        "accounts:login",
        "accounts:logout",
        "accounts:register_choice",
        "accounts:register_student",
        "accounts:register_teacher",
        "accounts:password_reset",
        "accounts:password_reset_done",
        "accounts:password_reset_confirm",
        "accounts:password_reset_complete",
    }
)


# The class that handles the middleware before students finish the diagnostic
class DiagnosticGateMiddleware:

    # A function to preserve requests so that it can be passed
    def __init__(self, get_response):
        self.get_response = get_response

    # A function to pass the request to the next handler
    def __call__(self, request):
        return self.get_response(request)

    # A function to redirect new students to the diagnostic page
    def process_view(self, request, view_func, view_args, view_kwargs):

        # Retrieve the user
        user = getattr(request, "user", None)

        # Validate if the user is a student: if not, then it will not redirect to the diagnostic page
        if user is None or not user.is_authenticated or not user.is_student:
            return None

        # Track the route that the student is trying to access
        match = request.resolver_match
        if match is None or match.app_name == "admin":
            return None

        # Check if the route is exempted from the diagnostic gate
        route = f"{match.namespace}:{match.url_name}" if match.namespace else match.url_name
        if route in EXEMPT_ROUTES:
            return None

        # Check if the student has completed the diagnostic
        if StudentProfile.objects.filter(
            student=user, diagnostic_completed_at__isnull=False
        ).exists():
            return None

        # If students do not fulfill the above conditions, they have to complete the diagnostic test
        return redirect("learning:diagnostic_intro")
