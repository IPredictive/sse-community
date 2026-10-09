import os
import sys

# cPanel Passenger entry point.
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from app import application as flask_application


class MountPathMiddleware:
    """Normalize requests for a Flask app mounted under /ipredict."""

    def __init__(self, app, prefix):
        self.app = app
        self.prefix = prefix.rstrip("/")

    def __call__(self, environ, start_response):
        path_info = environ.get("PATH_INFO", "") or "/"
        script_name = (environ.get("SCRIPT_NAME", "") or "").rstrip("/")

        # Some Passenger configurations leave the mount prefix in PATH_INFO.
        # Strip it so Flask can match routes such as /register and /health.
        if path_info == self.prefix:
            environ["PATH_INFO"] = "/"
            if not script_name:
                environ["SCRIPT_NAME"] = self.prefix
        elif path_info.startswith(self.prefix + "/"):
            environ["PATH_INFO"] = path_info[len(self.prefix):]
            if not script_name:
                environ["SCRIPT_NAME"] = self.prefix
        elif not script_name:
            # Passenger may already have stripped the prefix.
            environ["SCRIPT_NAME"] = self.prefix

        return self.app(environ, start_response)


application = MountPathMiddleware(flask_application, "/ipredict")
