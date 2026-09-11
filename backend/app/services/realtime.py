"""In-process realtime bus for Server-Sent Events (SSE).

The Flask dev server is threaded: every request (including each SSE stream)
runs in its own thread inside the single serving process. Writes and readers
therefore share this in-process broker, giving genuine server-push delivery
with no client-side polling.

publish() is called by any route that mutates state a user watches (status
changes, notifications, officer decisions, inspection reports, certificate
issuance). Subscribers are keyed by user id.
"""
import json
import queue
import threading

from ..models import now

_keeepalive_seconds = 15


class _Broker:
    def __init__(self):
        self._lock = threading.Lock()
        self._subs = {}  # user_id -> set(queue.Queue)

    def subscribe(self, user_id):
        q = queue.Queue(maxsize=64)
        with self._lock:
            self._subs.setdefault(user_id, set()).add(q)
        return q

    def unsubscribe(self, user_id, q):
        with self._lock:
            subs = self._subs.get(user_id)
            if subs:
                subs.discard(q)
                if not subs:
                    self._subs.pop(user_id, None)

    def publish(self, user_ids, event='update', payload=None):
        data = payload or {}
        data.setdefault('ts', now().isoformat())
        message = json.dumps({'event': event, 'data': data}, default=str)
        with self._lock:
            for uid in (u for u in user_ids if u):
                for q in list(self._subs.get(uid, ())):
                    try:
                        q.put_nowait(('event', message))
                    except queue.Full:
                        pass

    def publish_all(self, event='update', payload=None):
        data = payload or {}
        data.setdefault('ts', now().isoformat())
        message = json.dumps({'event': event, 'data': data}, default=str)
        with self._lock:
            for subs in self._subs.values():
                for q in list(subs):
                    try:
                        q.put_nowait(('event', message))
                    except queue.Full:
                        pass


_broker = _Broker()


def subscribe(user_id):
    return _broker.subscribe(user_id)


def unsubscribe(user_id, q):
    _broker.unsubscribe(user_id, q)


def publish(user_ids, event='update', payload=None):
    """Push an event to one or more users' live streams."""
    if not user_ids:
        return
    _broker.publish(list(user_ids), event=event, payload=payload)


def publish_all(event='update', payload=None):
    _broker.publish_all(event=event, payload=payload)


def sse_generator(user_id, q):
    """Generator yielding SSE frames; sends keepalive comments every 15s."""
    try:
        while True:
            try:
                kind, message = q.get(timeout=_keeepalive_seconds)
                if kind == 'event':
                    yield f"data: {message}\n\n"
            except queue.Empty:
                yield ": keepalive\n\n"
    finally:
        unsubscribe(user_id, q)