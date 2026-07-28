from django.urls import path

from core import views

urlpatterns = [
    path("", views.index, name="index"),
    path("tests/<int:case_id>/", views.test_detail, name="test_detail"),
    path("tests/<int:case_id>/quarantine/", views.toggle_quarantine, name="toggle_quarantine"),
    path("clusters/<int:cluster_id>/diagnose/", views.trigger_diagnosis, name="trigger_diagnosis"),
    path("agent-runs/<int:run_id>/", views.agent_run_detail, name="agent_run_detail"),
]
