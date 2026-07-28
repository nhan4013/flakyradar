from django.urls import path

from core import views

urlpatterns = [
    path("", views.index, name="index"),
    path("tests/<int:case_id>/", views.test_detail, name="test_detail"),
    path("tests/<int:case_id>/quarantine/", views.toggle_quarantine, name="toggle_quarantine"),
]
