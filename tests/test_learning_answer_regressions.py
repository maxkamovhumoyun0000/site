import pytest
from backend import library_ai, personalization


@pytest.mark.parametrize('short,full', [
    ("what's", 'what is'), ("What’s your name?", 'What is your name?'),
    ("I'm", 'I am'), ("we're", 'we are'), ("don't", 'do not'),
    ("can't", 'cannot'), ("I've", 'I have'), ("he'll", 'he will'),
])
def test_equivalent_answers(short, full):
    assert personalization._learning_answer_matches(short, [full])
    assert personalization._learning_answer_matches(full, [short])
    assert library_ai._norm_text(short) == library_ai._norm_text(full)


def test_equivalence_does_not_accept_different_subjects_or_possessives():
    assert not personalization._learning_answer_matches("he's", ["she's"])
    assert not personalization._learning_answer_matches("John's book", ['John is book'])


def test_free_text_alternatives_survive_both_authoring_pipelines():
    raw = {'kind': 'gap_fill', 'prompt': '___ your name?', 'answer': "What's",
           'accepted_answers': ['What is']}
    library = library_ai._normalize_questions([raw])[0]
    learning = personalization._learning_ai_question_payload(raw, topic='Greetings', position=1)
    assert 'What is' in library['accepted_answers']
    assert 'What is' in learning['accepted_answers']


@pytest.mark.parametrize('mode', ['read_aloud', 'speak_sentence', 'write_sentence', 'translation', 'spelling', 'matching'])
def test_random_vocabulary_replaces_stale_question_and_keeps_task_content(mode):
    source = {'kind': 'word_practice', 'word': 'hello (n)',
              'question': "So'z turi", 'prompt': "So'zni o'rganing.",
              'translation_uz': 'salom', 'translation_ru': 'привет',
              'translation_reverse': False}
    result = {**source, **library_ai._materialize_word_practice(source, chosen_kind=mode)}
    assert result['question'] == result['prompt']
    assert result['question'] != source['question']
    assert '(n)' not in result['question']
    if mode not in {'spelling', 'matching'}:
        assert 'hello' in result['question']
    if mode == 'spelling':
        assert 'hello' not in result['question']
        assert result['word'] == 'hello'  # supplied to TTS
    if mode == 'matching':
        assert result['pairs'][0] == {'left': 'hello', 'right': 'salom'}


def test_reverse_translation_shows_source_and_hides_target():
    result = library_ai._materialize_word_practice({
        'word': 'hello', 'question': 'stale', 'translation_uz': 'salom',
        'translation_reverse': True,
    }, chosen_kind='translation')
    assert 'salom' in result['question']
    assert 'hello' not in result['question']
    assert result['word'] is None
