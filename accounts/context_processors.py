"""
This file provides HTML templates with two variables: is_teacher and is_student
"""

# A function to return the user type for each request
def role_flags(request):

    # Check the current user type
    user = getattr(request, "user", None)

    # If the user has login to the system
    if user is not None and user.is_authenticated:
        return {"is_teacher": user.is_teacher, "is_student": user.is_student}

    # If the user is invalid, then both flags are false
    return {"is_teacher": False, "is_student": False}
