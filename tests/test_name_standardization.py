import pytest


def test_new_name_requires_latin_and_is_stored_uppercase():
    from name_standardization import normalize_new_latin_name

    assert normalize_new_latin_name("Xumoyun", "first_name") == "XUMOYUN"
    assert normalize_new_latin_name("O‘g‘il-oy", "last_name") == "O'G'IL-OY"
    with pytest.raises(ValueError, match="Latin"):
        normalize_new_latin_name("Хумоюн", "first_name")


def test_legacy_cyrillic_is_transliterated_and_standardized_for_audit():
    from name_standardization import standardize_legacy_name

    assert standardize_legacy_name("Хумоюн") == "HUMOYUN"
    assert standardize_legacy_name("Ғаниев") == "G'ANIEV"


def test_name_search_includes_x_and_h_variants():
    from name_standardization import name_search_terms

    assert {"XUMOYUN", "HUMOYUN"}.issubset(set(name_search_terms("Xumoyun")))
    assert {"XUMOYUN", "HUMOYUN"}.issubset(set(name_search_terms("Humoyun")))


def test_potential_duplicate_key_groups_x_and_h_spellings_only_as_potential():
    from name_standardization import potential_duplicate_key

    assert potential_duplicate_key("XUMOYUN", "KARIMOV") == potential_duplicate_key("HUMOYUN", "KARIMOV")


def test_audit_marks_exact_and_x_h_spelling_duplicates_separately():
    from scripts.standardize_user_names import audit_rows, duplicate_groups

    audited = audit_rows([
        {"id": 1, "login_id": "STU1", "login_type": 2, "first_name": "Хумоюн", "last_name": "Каримов"},
        {"id": 2, "login_id": "STU2", "login_type": 2, "first_name": "Humoyun", "last_name": "Karimov"},
        {"id": 3, "login_id": "STU3", "login_type": 2, "first_name": "Xumoyun", "last_name": "Karimov"},
    ])

    assert "HUMOYUN|KARIMOV" in duplicate_groups(audited, "exact_key", potential_only=False)
    assert "HUMOYUN|KARIMOV" in duplicate_groups(audited, "potential_key", potential_only=True)
