"""config – project-wide settings and static data."""
from .settings.settings import *          # noqa: F401,F403
from .settings.app_registry import SPECIAL_APPS, PROCESS_ALIASES  # noqa: F401
from .settings import settings            # noqa: F401  (allow `from config import settings`)
