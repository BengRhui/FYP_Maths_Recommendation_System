"""
This file maps the URL routes to the views of the learning app.
"""

from django.urls import path

from . import views

# Name of the app
app_name = "learning"

# URL routes for the learning app
urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("learning-path/", views.learning_path, name="learning_path"),
    path("activity/", views.activity, name="activity"),
    path("skill/<slug:slug>/", views.skill_detail, name="skill_detail"),
    path("skill/<slug:slug>/notes/", views.learn_notes, name="learn_notes"),
    path("skill/<slug:slug>/practice/", views.practice_start, name="practice_start"),
    path("practice/<int:session_id>/", views.practice_question, name="practice_question"),
    path("practice/<int:session_id>/answer/", views.practice_answer, name="practice_answer"),
    path("practice/<int:session_id>/exit/", views.practice_exit, name="practice_exit"),
    path("practice/<int:session_id>/results/", views.practice_results, name="practice_results"),
    path("diagnostic/", views.diagnostic_intro, name="diagnostic_intro"),
    path("diagnostic/start/", views.diagnostic_start, name="diagnostic_start"),
    path("diagnostic/<int:session_id>/", views.diagnostic_question, name="diagnostic_question"),
    path("diagnostic/<int:session_id>/results/", views.diagnostic_results, name="diagnostic_results"),
]
