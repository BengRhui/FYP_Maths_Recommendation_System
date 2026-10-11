"""
This file maps the URL paths to the different backend functions of classes.
"""

from django.urls import path

from . import views

# The URL domain
app_name = "classes"

# Map each URL to the respective functions
urlpatterns = [
    path("<int:class_id>/restrictions/", views.toggle_restrictions, name="toggle_restrictions"),
    path("teacher/", views.teacher_dashboard, name="teacher_dashboard"),
    path("teacher/classes/", views.teacher_classes, name="teacher_classes"),
    path("teacher/create/", views.create_class, name="create_class"),
    path("teacher/<int:class_id>/", views.class_detail, name="class_detail"),
    path("teacher/<int:class_id>/delete/", views.delete_class, name="delete_class"),
    path("teacher/<int:class_id>/topic/", views.toggle_topic, name="toggle_topic"),
    path("teacher/<int:class_id>/students/add/", views.add_student, name="add_student"),
    path(
        "teacher/<int:class_id>/student/<int:student_id>/remove/",
        views.remove_student,
        name="remove_student",
    ),
    path(
        "teacher/<int:class_id>/student/<int:student_id>/",
        views.student_detail,
        name="student_detail",
    ),
]
