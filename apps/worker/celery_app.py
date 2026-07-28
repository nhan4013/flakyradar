import os

import django
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

app = Celery("flakyradar")
app.conf.broker_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
app.conf.result_backend = os.environ.get("REDIS_URL", "redis://redis:6379/0")
app.autodiscover_tasks(["worker"])
