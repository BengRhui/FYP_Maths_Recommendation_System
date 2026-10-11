"""
The file defines the forms used for class management:
- Adding students
- Creating classes
"""

from django import forms

from .models import SchoolClass


# The class to handle adding students to a class
class AddStudentForm(forms.Form):

    # The email field required to add a student
    email = forms.EmailField(
        label="Student email",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control form-control-lg",
                "placeholder": "student@example.com",
                "autocomplete": "off",
            }
        ),
    )

    # A function to normalize / clean the submitted email before performing validation
    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


# The class to handle the form of creating a new class
class CreateClassForm(forms.ModelForm):

    # Show the settings for the create class form (pop up)
    class Meta:
        model = SchoolClass
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "e.g. Form 1 Amanah Mathematics",
                }
            )
        }
