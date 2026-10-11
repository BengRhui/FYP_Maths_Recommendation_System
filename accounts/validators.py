"""
This file defines how new passwords are validated.
"""

import re
from django.core.exceptions import ValidationError


# A class to define the alphabet requirements for passwords
class LetterValidator:

    # A function to require at least one letter in the password
    def validate(self, password, user=None):
        if not re.search(r"[a-zA-Z]", password):
            raise ValidationError(
                "Your password must contain at least one letter.",
                code="password_no_letter",
            )

    # A function to describe the requirement on password forms
    def get_help_text(self):
        return "Your password must contain at least one letter."


# A class to define the digit requirements for passwords
class NumberValidator:

    # A function to require at least one digit in the password
    def validate(self, password, user=None):
        if not re.search(r"[0-9]", password):
            raise ValidationError(
                "Your password must contain at least one number.",
                code="password_no_number",
            )

    # A function to describe the requirement on password forms
    def get_help_text(self):
        return "Your password must contain at least one number."


# A class to define the special character requirements for password
class SpecialCharacterValidator:

    # A function to require at least one non-alphanumeric character in the password
    def validate(self, password, user=None):
        if not re.search(r"[^a-zA-Z0-9]", password):
            raise ValidationError(
                "Your password must contain at least one special character.",
                code="password_no_special",
            )

    # A function to describe the requirement on password forms
    def get_help_text(self):
        return "Your password must contain at least one special character."
