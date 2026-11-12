from django.urls import path

from hospitals import views

urlpatterns = [
    path("api/hospitals", views.search),
]
