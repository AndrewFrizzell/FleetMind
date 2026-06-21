from functools import wraps
from flask import redirect, url_for, session

def login_required(view_func):
    @wraps(view_func)
    def wrapper (*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper
