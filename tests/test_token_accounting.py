import pytest
from lab.token_accounting import render_qwen, count_qwen


def test_qwen_template_preserves_source_and_closes_turns():
    messages = [{'role': 'system', 'content': 'rules'}, {'role': 'user', 'content': 'source\n"x"'}]
    assert render_qwen(messages) == '<|im_start|>system\nrules<|im_end|>\n<|im_start|>user\nsource\n"x"<|im_end|>\n<|im_start|>assistant\n'


def test_unvalidated_chat_layout_is_rejected():
    with pytest.raises(ValueError):
        render_qwen([{'role': 'user', 'content': 'x'}])


def test_unvalidated_tokenizer_is_rejected_before_loading(tmp_path):
    path = tmp_path / 'tokenizer.json'
    path.write_text('{}')
    with pytest.raises(ValueError, match='pinned'):
        count_qwen([], path)
