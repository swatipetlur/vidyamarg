from .utils import fmt_date, fmt_datetime, registration_state, rupees


def init_app(app):
    app.jinja_env.filters["rupees"] = rupees
    app.jinja_env.filters["date"] = fmt_date
    app.jinja_env.filters["datetime"] = fmt_datetime
    app.jinja_env.globals["registration_state"] = registration_state
    app.jinja_env.globals["payment_provider"] = lambda: app.config["PAYMENT_PROVIDER"]
