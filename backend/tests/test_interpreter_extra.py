"""Additional interpreter tests covering nested blocks and edge cases."""

from backend.ecolang.interpreter import Interpreter


def test_nested_if_else():
    it = Interpreter()
    code = (
        'let a = 2\n'
        'if a > 0 then\n'
        '  if a == 2 then\n'
        '    say "inner-yes"\n'
        '  else\n'
        '    say "inner-no"\n'
        '  end\n'
        'else\n'
        '  say "outer-no"\n'
        'end\n'
    )
    res = it.run(code)
    assert 'inner-yes' in res['output']
    assert res['errors'] is None


def test_repeat_step_limit_triggers_warning():
    it = Interpreter()
    it.max_steps = 5
    # many simple statements to exceed step limit
    code = '\n'.join(['say "x"' for _ in range(20)])
    res = it.run(code)
    assert any('Step limit exceeded' in w for w in res['warnings']) or any('Step limit exceeded' in w for w in res['warnings'])


def test_savepower_persistence_and_warning():
    it = Interpreter()
    code = 'savePower 30\nsay 1'
    res = it.run(code)
    assert any('savePower applied' in w for w in res['warnings'])
    assert '1' in res['output']


def test_missing_ask_input_returns_error():
    it = Interpreter()
    code = 'ask missing\nsay missing'
    res = it.run(code)
    assert res['errors'] is not None
    assert res['errors'].get('code') == 'RUNTIME_ERROR'


def test_syntax_error_missing_end():
    it = Interpreter()
    code = 'if true then\n  say 1\n'
    res = it.run(code)
    assert res['errors'] is not None
    assert res['errors'].get('code') == 'SYNTAX_ERROR'


def test_eco_metrics_present():
    it = Interpreter()
    res = it.run('say "hi"')
    assert res['errors'] is None
    assert res['eco'] is not None
    assert isinstance(res['eco'].get('total_ops'), int)
    assert res['eco'].get('total_ops', 0) >= 0
