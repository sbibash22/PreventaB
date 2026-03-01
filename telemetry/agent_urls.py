from django.urls import path
from .agent_views import ingest

urlpatterns = [
    path("ingest/", ingest, name="agent_ingest"),
]
