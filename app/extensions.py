"""Flask extensions: created once and bound to the application in create_app()."""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect

csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)
