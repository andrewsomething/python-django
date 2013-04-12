import sys
import os

PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))

# redirect sys.stdout to sys.stderr for bad libraries like geopy that uses
# print statements for optional import exceptions.
sys.stdout = sys.stderr

sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, "apps"))
sys.path.insert(0, os.path.join(PROJECT_DIR, "external_apps"))

os.environ["DJANGO_SETTINGS_MODULE"] = "settings"

from django.core.handlers.wsgi import WSGIHandler
application = WSGIHandler()

