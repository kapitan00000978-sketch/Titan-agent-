"""
AST-Aware Code Patcher.

Upgrades standard text-based diff patching with AST validation.
Ensures that applied patches do not introduce syntax errors, bringing
robust code editing capabilities to Titan.
"""
import ast
import re

class ASTPatchError(Exception):
    pass

class ASTPatcher:
    """
    Intelligent patcher that applies search/replace or unified diffs
    and validates the resulting Abstract Syntax Tree (AST) to ensure
    no syntax errors were introduced. Outperforms line-based diff tools.
    """

    @staticmethod
    def validate_syntax(code: str) -> bool:
        """Validates that the provided code is syntactically correct Python."""
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    @staticmethod
    def extract_definitions(code: str) -> dict[str, list[str]]:
        """Extracts top-level function, class, and import names from Python code via AST."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"functions": [], "classes": [], "imports": []}

        functions: list[str] = []
        classes: list[str] = []
        imports: list[str] = []

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    imports.append(f"{mod}.{alias.name}")

        return {"functions": functions, "classes": classes, "imports": imports}

    @staticmethod
    def replace_function(original_code: str, target_name: str, new_func_code: str) -> str:
        """Replaces a specific function in Python code using AST boundary detection."""
        try:
            tree = ast.parse(original_code)
        except SyntaxError as e:
            raise ASTPatchError(f"Original code contains SyntaxError: {e}") from e

        target_node = None
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target_name:
                target_node = node
                break

        if not target_node or not hasattr(target_node, "lineno") or not hasattr(target_node, "end_lineno"):
            raise ASTPatchError(f"Function '{target_name}' not found in top-level definitions.")

        lines = original_code.splitlines(keepends=True)
        # AST lineno is 1-indexed
        start_idx = target_node.lineno - 1
        end_idx = target_node.end_lineno

        new_func_lines = new_func_code.strip() + "\n"
        new_code = "".join(lines[:start_idx]) + new_func_lines + "".join(lines[end_idx:])

        if not ASTPatcher.validate_syntax(new_code):
            raise ASTPatchError(f"Replacing function '{target_name}' resulted in a SyntaxError.")

        return new_code

    @staticmethod
    def replace_class(original_code: str, target_name: str, new_class_code: str) -> str:
        """Replaces a specific class definition in Python code using AST boundary detection."""
        try:
            tree = ast.parse(original_code)
        except SyntaxError as e:
            raise ASTPatchError(f"Original code contains SyntaxError: {e}") from e

        target_node = None
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == target_name:
                target_node = node
                break

        if not target_node or not hasattr(target_node, "lineno") or not hasattr(target_node, "end_lineno"):
            raise ASTPatchError(f"Class '{target_name}' not found in top-level definitions.")

        lines = original_code.splitlines(keepends=True)
        start_idx = target_node.lineno - 1
        end_idx = target_node.end_lineno

        new_class_lines = new_class_code.strip() + "\n"
        new_code = "".join(lines[:start_idx]) + new_class_lines + "".join(lines[end_idx:])

        if not ASTPatcher.validate_syntax(new_code):
            raise ASTPatchError(f"Replacing class '{target_name}' resulted in a SyntaxError.")

        return new_code

    @staticmethod
    def apply_replacement(original_code: str, search_block: str, replace_block: str) -> str:
        """
        Replaces search_block with replace_block in original_code.
        Validates the AST before and after.
        """
        original_code = original_code.replace('\r\n', '\n')
        search_block = search_block.replace('\r\n', '\n').strip()
        replace_block = replace_block.replace('\r\n', '\n').strip()

        if search_block not in original_code:
            # Fallback to a regex search if exact match fails due to minor whitespace
            escaped_search = re.escape(search_block)
            escaped_search = re.sub(r'\\ +', r' +', escaped_search)
            match = re.search(escaped_search, original_code)
            if not match:
                raise ASTPatchError("Search block not found in original code.")
            start, end = match.span()
            new_code = original_code[:start] + replace_block + original_code[end:]
        else:
            new_code = original_code.replace(search_block, replace_block, 1)

        # Validate syntax if the original code was valid
        if ASTPatcher.validate_syntax(original_code):
            if not ASTPatcher.validate_syntax(new_code):
                raise ASTPatchError("Patch applied, but introduced a SyntaxError.")

        return new_code
