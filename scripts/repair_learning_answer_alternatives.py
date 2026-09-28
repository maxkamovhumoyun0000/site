"""Reviewed alternatives for the existing Beginner module (dry-run by default).

Run after a database backup, with --apply to persist. Exact prompt guards and
compare-and-swap updates prevent overwriting edits made after this review.
"""
import argparse
import json
from backend import personalization as learning
from backend.answer_normalization import expand_english_contractions

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
REVIEWED = {
    598: ("A: How are you? B: I'm _____, thanks.", ['fine', 'well', 'good', 'OK', 'okay', 'great', 'not bad']),
    604: ('A: _____ I have a cappuccino, please?', ['Can', 'May', 'Could']),
    609: ('A: Hello. B: _____.', ['Hi', 'Hello', 'Hey', 'Good morning', 'Good afternoon', 'Good evening']),
    626: ('___ to meet you.', ['Nice', 'Pleased', 'Good', 'Great', 'Lovely', 'Delighted']),
    630: ('I ___ from France.', ["'m", 'am']),
    658: ('___ to meet you.', ['Nice', 'Pleased', 'Good', 'Great', 'Lovely', 'Delighted']),
    664: ('I ___ Anna.', ['am', "'m"]),
    670: ('___ name is Tom.', ['My', 'Your', 'His', 'Her', 'Their']),
    736: ('Write the word for 0: ___.', ['zero', 'nought', 'nil', 'oh']),
    774: ('The week starts on _____.', ['Sunday', 'Monday']),
    776: ('Today is _____.', DAYS),
    778: ('We have classes on _____.', DAYS),
    782: ('My favorite day is _____.', DAYS),
}


def repair(apply=False):
    conn = learning.get_conn()
    changed = []
    try:
        cur = conn.cursor()
        cur.execute('SELECT id,question_payload_json FROM learning_module_lessons WHERE module_id=? ORDER BY id', (30,))
        for record in cur.fetchall():
            row = dict(record)
            original = row['question_payload_json']
            question = json.loads(original or '{}')
            if question.get('kind') not in {'gap_fill', 'fill_blank'}:
                continue
            answer = str(question.get('correct_answer') or question.get('answer') or '')
            alternatives = [answer, *(question.get('accepted_answers') or [])]
            if row['id'] in REVIEWED:
                prompt, reviewed = REVIEWED[row['id']]
                if question.get('question') != prompt:
                    raise RuntimeError(f"Lesson {row['id']} changed since review; stop before writing")
                alternatives.extend(reviewed)
            alternatives.extend(expand_english_contractions(value) for value in list(alternatives))
            unique = {}
            for value in alternatives:
                if str(value).strip():
                    unique.setdefault(str(value).strip().casefold(), str(value).strip())
            alternatives = list(unique.values())
            if alternatives == question.get('accepted_answers') and alternatives == question.get('acceptable_answers'):
                continue
            question['accepted_answers'] = alternatives
            question['acceptable_answers'] = alternatives
            changed.append({'id': row['id'], 'accepted_answers': alternatives})
            if apply:
                cur.execute(
                    'UPDATE learning_module_lessons SET question_payload_json=? WHERE id=? AND question_payload_json=?',
                    (json.dumps(question, ensure_ascii=False), row['id'], original),
                )
                if cur.rowcount != 1:
                    raise RuntimeError('Concurrent lesson edit; rolling back')
        if apply:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if apply and changed:
        learning.rebuild_learning_path_library_mirrors()
    return {'applied': apply, 'changes': changed}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(repair(args.apply), ensure_ascii=False))
