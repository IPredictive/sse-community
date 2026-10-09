import os
import sys

# cPanel Passenger entry point.
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from app import application as flask_application


class MountPathMiddleware:
    """Make Flask generate URLs under the cPanel application's URL prefix."""

    def __init__(self, app, prefix):
        self.app = app
        self.prefix = prefix.rstrip("/")

    def __call__(self, environ, start_response):
        # Passenger may strip the mount path but leave SCRIPT_NAME empty.
        # Preserve it if the server has already set it correctly.
        if not environ.get("SCRIPT_NAME") or environ.get("SCRIPT_NAME") == "/":
            environ["SCRIPT_NAME"] = self.prefix
        return self.app(environ, start_response)


application = MountPathMiddleware(flask_application, "/ipredict")
