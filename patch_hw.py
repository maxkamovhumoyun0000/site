import re

with open('teacher_hw.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace _WEB_HW_STATE = {}
content = re.sub(
    r'_WEB_HW_STATE = \{\}',
    """import os
WEB_HW_STATE_DIR = "data/web_hw_state"
os.makedirs(WEB_HW_STATE_DIR, exist_ok=True)

def _get_web_hw_state(chat_id):
    path = os.path.join(WEB_HW_STATE_DIR, f"{chat_id}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return __import__('json').load(f)
        except:
            return None
    return None

def _set_web_hw_state(chat_id, state_dict):
    path = os.path.join(WEB_HW_STATE_DIR, f"{chat_id}.json")
    if state_dict is None:
        if os.path.exists(path):
            os.remove(path)
    else:
        with open(path, "w", encoding="utf-8") as f:
            __import__('json').dump(state_dict, f)""",
    content
)

# Replace state_dict = _WEB_HW_STATE.get(chat_id)
content = re.sub(
    r'state_dict = _WEB_HW_STATE\.get\(chat_id\)',
    'state_dict = _get_web_hw_state(chat_id)',
    content
)

# Replace _WEB_HW_STATE[chat_id] = {'step': 'dhw_group', 'data': {}}
content = re.sub(
    r"_WEB_HW_STATE\[chat_id\] = \{'step': 'dhw_group', 'data': \{\}\}",
    "state_dict = {'step': 'dhw_group', 'data': {}}\n            _set_web_hw_state(chat_id, state_dict)",
    content
)

# Replace del _WEB_HW_STATE[chat_id]
content = re.sub(
    r'del _WEB_HW_STATE\[chat_id\]',
    '_set_web_hw_state(chat_id, None)',
    content
)

# Insert _set_web_hw_state after step/data modifications
modifications = [
    (r"state_dict\['step'\] = 'dhw_deadline'", r"state_dict['step'] = 'dhw_deadline'\n        _set_web_hw_state(chat_id, state_dict)"),
    (r"state_dict\['step'\] = 'dhw_comment'", r"state_dict['step'] = 'dhw_comment'\n        _set_web_hw_state(chat_id, state_dict)"),
    (r"state_dict\['step'\] = 'dhw_files'", r"state_dict['step'] = 'dhw_files'\n        _set_web_hw_state(chat_id, state_dict)"),
    (r"state_dict\['step'\] = 'dhw_test_method'", r"state_dict['step'] = 'dhw_test_method'\n                _set_web_hw_state(chat_id, state_dict)"),
    (r"state_dict\['data'\]\['req_test'\] = req_test", r"state_dict['data']['req_test'] = req_test\n        _set_web_hw_state(chat_id, state_dict)"),
    (r"state_dict\['step'\] = 'dhw_ai_test_gen'", r"state_dict['step'] = 'dhw_ai_test_gen'\n            _set_web_hw_state(chat_id, state_dict)"),
    (r"state_dict\['step'\] = 'dhw_wait_tests'", r"state_dict['step'] = 'dhw_wait_tests'\n            _set_web_hw_state(chat_id, state_dict)"),
    (r"state_dict\['step'\] = 'dhw_tests_or_finish'", r"state_dict['step'] = 'dhw_tests_or_finish'\n            _set_web_hw_state(chat_id, state_dict)")
]

for pattern, repl in modifications:
    content = re.sub(pattern, repl, content)

with open('teacher_hw.py', 'w', encoding='utf-8') as f:
    f.write(content)
