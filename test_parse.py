import ai_generator

json_text = """```json
[{"word":"test","translation_uz":"sinov","translation_ru":"испытание","definition":"a procedure to establish quality","example":"This is a test"}]
```"""

print(ai_generator.parse_vocabulary_json(json_text, "English", "A1"))
