from forge.bootstrap import build_container


def test_build_container_falls_back_to_in_memory_store_when_supabase_missing(settings) -> None:
    empty_settings = settings.__class__(**{**settings.__dict__, "supabase_url": "", "supabase_key": ""})

    container = build_container(empty_settings)

    assert container.store.__class__.__name__ == "InMemoryStore"
