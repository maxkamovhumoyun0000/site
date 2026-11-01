import ai_generator


def test_gamified_material_is_kept_in_the_selected_subject_language():
    assert ai_generator._gamified_text_matches_subject("Russian", "Она читает книгу.")
    assert not ai_generator._gamified_text_matches_subject("Russian", "She reads a book.")
    assert ai_generator._gamified_text_matches_subject("English", "She reads a book.")
    assert not ai_generator._gamified_text_matches_subject("English", "Она читает книгу.")
