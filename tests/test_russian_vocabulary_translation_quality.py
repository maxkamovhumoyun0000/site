import ai_generator


def test_russian_placeholder_translation_is_sent_for_ai_repair():
    item = {
        "word": "задание",
        "translation_uz": "задание so'zi",
        "translation_ru": "задание",
        "definition": "Задание — это работа, которую выполняют для обучения или проверки знаний.",
        "example": "Сегодня учитель дал нам интересное задание по русскому языку.",
    }

    assert ai_generator._needs_vocab_quality_repair(item, "Russian") is True
