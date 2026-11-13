from flask import g, session

from ..utils import parse_standard


def remembered_standard():
    """The standard saved in this browser session, or on the student's profile."""
    value = session.get("standard")
    if value is None and g.get("user") is not None:
        value = g.user["current_standard"]
        if value:
            session["standard"] = value
    return parse_standard(value)
