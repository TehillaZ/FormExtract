import pytest

from app.api.main import app
from app.auth import current_role


@pytest.fixture(autouse=True)
def logged_in_as_developer(request):
    """Tests of the API are not about logging in: they act as a developer. test_auth.py turns this off."""
    if request.module.__name__.endswith("test_auth"):
        yield
        return
    app.dependency_overrides[current_role] = lambda: "developer"
    yield
    app.dependency_overrides.pop(current_role, None)
