"""Free-tier quotas are per model and can be daily: do not wait hours, and do not waste calls on a spent model."""
import httpx
import pytest

from app.vision import base
from app.vision.base import RateLimited, post_with_backoff, retry_after_seconds
from app.vision.gemini import GeminiProvider

DAILY = ("You exceeded your current quota. * Quota exceeded for metric: generate_content_free_tier_requests, "
         "limit: 20, model: gemini-2.5-flash\nPlease retry in 17h43m30.914275847s.")


def response(status: int, text: str = "", headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status, text=text, headers=headers or {}, request=httpx.Request("POST", "https://x/y"))


class ScriptedClient:
    """Answers each post with the next scripted response."""

    def __init__(self, *responses: httpx.Response):
        self.responses, self.calls = list(responses), 0

    async def post(self, url, **kw):
        self.calls += 1
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    slept: list[float] = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(base.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(base.settings, "min_call_interval", 0.0)
    return slept


class TestRetryAfter:
    def test_reads_hours_minutes_seconds_from_the_message(self):
        assert retry_after_seconds(response(429, DAILY)) == pytest.approx(17 * 3600 + 43 * 60 + 30.914, rel=1e-4)

    def test_reads_plain_seconds(self):
        assert retry_after_seconds(response(429, "Please retry in 42.5s")) == 42.5

    def test_prefers_the_header(self):
        assert retry_after_seconds(response(429, DAILY, {"retry-after": "7"})) == 7

    def test_none_when_the_provider_says_nothing(self):
        assert retry_after_seconds(response(429, "slow down")) is None


class TestBackoff:
    async def test_a_daily_quota_gives_up_at_once_without_sleeping(self, no_waiting):
        client = ScriptedClient(response(429, DAILY))
        with pytest.raises(RateLimited) as e:
            await post_with_backoff(client, "https://x/y")
        assert client.calls == 1 and no_waiting == []
        assert e.value.retry_after and e.value.retry_after > 3600

    async def test_a_short_wait_is_waited_out_and_retried(self, no_waiting):
        client = ScriptedClient(response(429, "Please retry in 12s"), response(200, "{}"))
        r = await post_with_backoff(client, "https://x/y")
        assert r.status_code == 200 and client.calls == 2 and no_waiting == [12.0]

    async def test_without_a_hint_it_backs_off_exponentially_then_gives_up(self, no_waiting):
        client = ScriptedClient(*[response(429, "busy")] * 3)
        with pytest.raises(RateLimited):
            await post_with_backoff(client, "https://x/y", retries=2)
        assert no_waiting == [10.0, 20.0]

    async def test_a_server_error_is_retried(self, no_waiting):
        client = ScriptedClient(response(503, "down"), response(200, "{}"))
        assert (await post_with_backoff(client, "https://x/y")).status_code == 200


class TestGeminiFallback:
    def provider(self, monkeypatch, outcomes: dict):
        """A provider whose per-model result is scripted: a RateLimited to raise, or the answer text."""
        calls: list[str] = []

        async def fake_post(client, url, **kw):
            model = url.split("/models/")[1].split(":")[0]
            calls.append(model)
            outcome = outcomes[model]
            if isinstance(outcome, Exception):
                raise outcome
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": outcome}]}}]},
                                  request=httpx.Request("POST", url))

        monkeypatch.setattr("app.vision.gemini.post_with_backoff", fake_post)
        return GeminiProvider("m1", ["m2", "m3"]), calls

    async def test_uses_the_first_model_when_it_has_quota(self, monkeypatch):
        p, calls = self.provider(monkeypatch, {"m1": "one", "m2": "two", "m3": "three"})
        assert await p._complete("s", "u", b"x") == "one" and calls == ["m1"]

    async def test_moves_to_the_next_model_when_one_is_out_of_quota(self, monkeypatch):
        p, calls = self.provider(monkeypatch, {"m1": RateLimited("x", 3600), "m2": "two", "m3": "three"})
        assert await p._complete("s", "u", b"x") == "two" and calls == ["m1", "m2"]

    async def test_remembers_a_spent_model_and_does_not_call_it_again(self, monkeypatch):
        p, calls = self.provider(monkeypatch, {"m1": RateLimited("x", 3600), "m2": "two", "m3": "three"})
        await p._complete("s", "u", b"x")
        await p._complete("s", "u", b"x")
        assert calls == ["m1", "m2", "m2"]

    async def test_raises_when_every_model_is_spent(self, monkeypatch):
        spent = RateLimited("x", 3600)
        p, _ = self.provider(monkeypatch, {"m1": spent, "m2": spent, "m3": spent})
        with pytest.raises(RateLimited):
            await p._complete("s", "u", b"x")
        with pytest.raises(RateLimited):          # and stays that way while all are cooling down
            await p._complete("s", "u", b"x")

    def test_the_fallback_list_comes_from_settings_and_never_repeats_the_primary(self):
        p = GeminiProvider("a", ["a", "b"])
        assert p.models == ["a", "b"]


def test_the_default_model_order_puts_the_fast_measured_model_first_and_the_slow_one_last():
    """gemini-2.5-flash was the most accurate on the shared pages and takes about 12 s a page; gemini-3.5-flash takes
    about 100 s, which makes a 30-form batch take close to an hour. Changing this order is a decision, not a tweak."""
    from app.config import Settings
    settings = Settings(_env_file=None)
    models = [settings.gemini_model, *settings.gemini_fallback_models]
    assert models[0] == "gemini-2.5-flash" and models[-1] == "gemini-3.5-flash"
    assert len(set(models)) == len(models)
