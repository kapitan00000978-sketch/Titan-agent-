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

def test_ast_patcher_replace_function():
    code = "import os\n\ndef add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n"
    new_add = "def add(a, b):\n    return (a + b) * 2"
    result = ASTPatcher.replace_function(code, "add", new_add)
    assert "* 2" in result
    assert "def sub" in result
    assert ASTPatcher.validate_syntax(result) is True

def test_ast_patcher_replace_class():
    code = "class Calculator:\n    def calculate(self):\n        return 1\n"
    new_class = "class Calculator:\n    def calculate(self):\n        return 99\n"
    result = ASTPatcher.replace_class(code, "Calculator", new_class)
    assert "return 99" in result
    assert ASTPatcher.validate_syntax(result) is True

def test_ast_patcher_extract_definitions():
    code = "import math\nfrom pathlib import Path\n\nclass Foo:\n    pass\n\ndef bar():\n    pass\n"
    defs = ASTPatcher.extract_definitions(code)
    assert "bar" in defs["functions"]
    assert "Foo" in defs["classes"]
    assert "math" in defs["imports"]

