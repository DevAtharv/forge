from forge.memory.context import build_user_context
from forge.schemas import ConversationRecord, UserProfile


def test_build_user_context_hybrid_policy_includes_profile_and_summary() -> None:
    profile = UserProfile(
        user_id=1,
        username="alice",
        stack=["Python", "FastAPI"],
        summary="Working on a Telegram bot.",
        active_context={"current_goal": "implement webhook queue"},
    )
    history = [
        ConversationRecord(user_id=1, role="user", content="I want a queue."),
        ConversationRecord(user_id=1, role="assistant", content="We can use Postgres locking."),
    ]

    context = build_user_context(profile, history, "recent_plus_profile_plus_summary")

    assert "Python, FastAPI" in context
    assert "Persistent summary: Working on a Telegram bot." in context
    assert "user: I want a queue." in context
