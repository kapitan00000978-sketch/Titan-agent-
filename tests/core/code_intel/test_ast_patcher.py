import pytest
from titan_agent.core.code_intel.ast_patcher import ASTPatcher, ASTPatchError

def test_ast_patcher_valid_syntax():
    assert ASTPatcher.validate_syntax("def foo():\n    return 42") is True
    assert ASTPatcher.validate_syntax("def foo(): return") is True
    assert ASTPatcher.validate_syntax("def foo() return") is False

def test_ast_patcher_apply_replacement():
    original = "def foo():\n    return 42\n"
    search = "return 42"
    replace = "return 100"
    
    new_code = ASTPatcher.apply_replacement(original, search, replace)
    assert "return 100" in new_code
    assert ASTPatcher.validate_syntax(new_code) is True

def test_ast_patcher_syntax_error_prevention():
    original = "def foo():\n    return 42\n"
    search = "return 42"
    replace = "return 42 if" # invalid syntax
    
    with pytest.raises(ASTPatchError, match="SyntaxError"):
        ASTPatcher.apply_replacement(original, search, replace)

def test_ast_patcher_not_found():
    original = "def foo():\n    return 42\n"
    search = "return 100"
    replace = "return 200"
    
    with pytest.raises(ASTPatchError, match="not found"):
        ASTPatcher.apply_replacement(original, search, replace)
