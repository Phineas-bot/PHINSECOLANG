from backend.ecolang.interpreter import Interpreter


def test_say_and_let():
    it = Interpreter()
    code = 'let x = 5\nlet y = x + 3\nsay "Result:"\nsay y'
    res = it.run(code)
    assert 'Result:' in res['output']
    assert '8' in res['output']
    assert res['errors'] is None


def test_if_and_repeat_warn_eco():
    it = Interpreter()
    code = (
        'let a = 1\n'
        'if a == 1 then\n'
        '  say "yes"\n'
        'else\n'
        '  say "no"\n'
        'end\n'
        'repeat 3 times\n'
        '  warn "looping"\n'
        '  say "loop"\n'
        'end\n'
        'ecoTip\n'
    )
    res = it.run(code)
    assert 'yes' in res['output']
    assert res['output'].count('loop') == 3
    assert any('looping' in w for w in res['warnings']) or res['warnings']
    assert 'ecoTip:' in res['output']


def test_ask_and_savepower():
    it = Interpreter()
    code = 'ask answer\nsay answer\nsavePower 30\nsay 1+1'
    res = it.run(code, inputs={'answer': 'green'})
    assert 'green' in res['output']
    assert '2' in res['output']
