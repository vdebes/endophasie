from server import parse_request


def test_full_request():
    assert parse_request("/run/rec.wav\tfr\tLe texte d'avant.\n") == (
        "/run/rec.wav", "fr", "Le texte d'avant.")


def test_older_clients_send_fewer_fields():
    assert parse_request("/run/rec.wav\n") == ("/run/rec.wav", "", "")
    assert parse_request("/run/rec.wav\ten\n") == ("/run/rec.wav", "en", "")
