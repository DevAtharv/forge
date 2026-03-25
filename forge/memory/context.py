from __future__ import annotations

from forge.schemas import ConversationRecord, UserProfile


def build_user_context(
    profile: UserProfile,
    history: list[ConversationRecord],
    policy: str,
) -> str:
    sections: list[str] = []
    if policy in {"recent_plus_profile", "recent_plus_profile_plus_summary"}:
        stack = ", ".join(profile.stack) if profile.stack else "unknown"
        projects = ", ".join(profile.current_projects) if profile.current_projects else "none recorded"
        sections.append(f"User profile: skill={profile.skill_level}; stack={stack}; projects={projects}.")
        if profile.preferences:
            sections.append(f"Preferences: {profile.preferences}.")
    if policy == "recent_plus_profile_plus_summary" and profile.summary:
        sections.append(f"Persistent summary: {profile.summary}")
        if profile.active_context:
            sections.append(f"Active context: {profile.active_context}")

    if history:
        transcript = []
        for item in history[-8:]:
            snippet = item.content.replace("\n", " ").strip()
            transcript.append(f"{item.role}: {snippet[:240]}")
        sections.append("Recent conversation:\n" + "\n".join(transcript))

    return "\n\n".join(section for section in sections if section.strip())
