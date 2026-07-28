import os

import django
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

app = Celery("flakyradar")
app.conf.broker_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
app.conf.result_backend = os.environ.get("REDIS_URL", "redis://redis:6379/0")
# diagnose (Phase 3 sandboxed agent) needs docker.sock — routed to a queue only the
# opt-in `agent` service consumes, so the ingest worker never touches the host docker
app.conf.task_routes = {"worker.diagnose": {"queue": "diagnose"}}
app.autodiscover_tasks(["worker"])
