from django.urls import path

from triage import views

urlpatterns = [
    path("api/triage/sessions", views.create_session),
    path("api/triage/sessions/<str:session_id>/messages", views.post_message),
    path("api/triage/sessions/<str:session_id>/result", views.get_result),
]
