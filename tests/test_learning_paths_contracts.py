import backend.personalization as personalization


def test_track_passing_score_defaults_to_seventy_and_is_clamped():
    assert personalization.normalize_track_passing_score(None) == 70
    assert personalization.normalize_track_passing_score(70) == 70
    assert personalization.normalize_track_passing_score(101) == 100
    assert personalization.normalize_track_passing_score(0) == 1


def test_module_and_next_track_unlock_require_passing_score():
    assert personalization.learning_score_passes(69.99, 70) is False
    assert personalization.learning_score_passes(70, 70) is True
    assert personalization.next_track_unlocked(["passed", "passed"]) is True
    assert personalization.next_track_unlocked(["passed", "in_progress"]) is False


def test_certificate_is_eligible_only_after_track_completion():
    assert personalization.track_certificate_eligible("passed", certificate_required=True) is True
    assert personalization.track_certificate_eligible("in_progress", certificate_required=True) is False
    assert personalization.track_certificate_eligible("passed", certificate_required=False) is False
