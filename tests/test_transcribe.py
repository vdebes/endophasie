from transcribe import pick_language


class FakeModel:
    """Language detection that hears French first, then English."""

    def detect_language(self, audio, vad_filter):
        return "fr", 0.6, [("fr", 0.6), ("nl", 0.3), ("en", 0.1)]


def test_auto_lets_whisper_detect():
    assert pick_language(FakeModel(), None, "auto") is None


def test_one_language_is_forced():
    assert pick_language(FakeModel(), None, "en") == "en"


def test_a_list_restricts_detection():
    # Dutch scores higher than English, but is not in the list.
    assert pick_language(FakeModel(), None, "en,nl") == "nl"
    assert pick_language(FakeModel(), None, " en , de ") == "en"
