import os

# Must run before `app.main` (and therefore `app.auth`) is imported by any
# test module -- auth.py reads SUBTITLE_SERVICE_API_KEY at import time and
# raises if it's unset. conftest.py is collected first by pytest, which is
# what makes that ordering safe here.
os.environ.setdefault('SUBTITLE_SERVICE_API_KEY', 'test-key-do-not-use-in-prod')
