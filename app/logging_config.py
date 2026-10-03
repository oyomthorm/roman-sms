"""
Structured logging.

In production (LOG_FORMAT=json) every log line is a JSON object. In dev
the default human-readable format is used. A request id is attached to
each request and included in every log line emitted during that request.
"""
import json
import logging
import sys
import uuid
from datetime import datetime

from flask import g, request


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            'ts': datetime.utcfromtimestamp(record.created).isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'msg': record.getMessage(),
        }
        request_id = getattr(g, 'request_id', None) if _has_app_context() else None
        if request_id:
            payload['request_id'] = request_id
        if record.exc_info:
            payload['exc'] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _has_app_context():
    try:
        return bool(g)
    except Exception:
        return False


def configure_logging(app):
    fmt = app.config.get('LOG_FORMAT', 'text')
    level = app.config.get('LOG_LEVEL', 'INFO')
    handler = logging.StreamHandler(sys.stdout)

    if fmt == 'json':
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s'))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Keep SQLAlchemy quiet unless explicitly requested.
    logging.getLogger('sqlalchemy.engine').setLevel('WARNING')

    if fmt == 'json':
        @app.before_request
        def _attach_request_id():
            g.request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())

        @app.after_request
        def _echo_request_id(response):
            if hasattr(g, 'request_id'):
                response.headers['X-Request-ID'] = g.request_id
            return response