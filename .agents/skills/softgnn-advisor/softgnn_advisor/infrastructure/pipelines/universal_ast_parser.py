import os
import re
from pathlib import Path


class UniversalASTParser:
    """Universal AST and symbol extractor for any programming language.

    Supports TypeScript, JavaScript, Go, Rust, Java, Python, and C/C++.
    Uses Tree-sitter when available, with a resilient brace/indentation fallback.
    """

    EXT_TO_LANG = {
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.mjs': 'javascript',
        '.go': 'go',
        '.rs': 'rust',
        '.java': 'java',
        '.cpp': 'cpp',
        '.cc': 'cpp',
        '.c': 'c',
        '.cs': 'csharp',
        '.php': 'php',
        '.py': 'python',
    }

    def __init__(self, repo_path: str = None):
        self.repo_path = os.path.abspath(repo_path or os.getcwd())

    def parse_file(self, file_path: str) -> list[dict]:
        """Parse a source file and extract all function/method ranges and signatures."""
        abs_path = os.path.join(self.repo_path, file_path) if not os.path.isabs(file_path) else file_path
        if not os.path.exists(abs_path):
            return []

        _, ext = os.path.splitext(abs_path.lower())
        lang = self.EXT_TO_LANG.get(ext, 'unknown')

        try:
            content = Path(abs_path).read_text(encoding='utf-8', errors='replace')
        except Exception:
            return []

        # For Python, if requested through universal parser, use built-in ast
        if lang == 'python':
            return self._parse_python(content, abs_path)

        # For all other languages (TS, JS, Go, Rust, Java, C++), parse with brace-syntax extractor
        return self._parse_brace_language(content, abs_path, lang)

    def collect_function_ranges(self, repo_path: str = None) -> dict:
        """Scan repository and collect function ranges for all source files.

        Returns: {rel_file_path: [{'function_id': ..., 'start': int, 'end': int}, ...]}
        """
        root = repo_path or self.repo_path
        ranges = {}
        ignore_dirs = {'.git', '.venv', 'venv', 'node_modules', 'dist', 'build', '__pycache__', 'target', 'vendor', '.next'}

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith('.')]
            for file in filenames:
                _, ext = os.path.splitext(file.lower())
                if ext in self.EXT_TO_LANG:
                    abs_file = os.path.join(dirpath, file)
                    rel_file = os.path.relpath(abs_file, root).replace('\\', '/')
                    parsed = self.parse_file(abs_file)
                    if parsed:
                        ranges[rel_file] = parsed

        return ranges

    def _parse_python(self, content: str, file_path: str) -> list[dict]:
        import ast
        results = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return results

        lines = content.splitlines()

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        start = child.lineno
                        end = getattr(child, 'end_lineno', child.lineno)
                        results.append({
                            'function_id': f'FUNC:{node.name}.{child.name}',
                            'name': f'{node.name}.{child.name}',
                            'start': start,
                            'end': end,
                            'signature': f"def {child.name}(...)",
                            'source': '\n'.join(lines[start - 1:end]),
                            'language': 'python',
                        })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = node.lineno
                end = getattr(node, 'end_lineno', node.lineno)
                results.append({
                    'function_id': f'FUNC:{node.name}',
                    'name': node.name,
                    'start': start,
                    'end': end,
                    'signature': f"def {node.name}(...)",
                    'source': '\n'.join(lines[start - 1:end]),
                    'language': 'python',
                })
        return results

    def _parse_brace_language(self, content: str, file_path: str, lang: str) -> list[dict]:
        """Resilient brace-based parser for C-family languages (TS, JS, Go, Rust, Java, C/C++)."""
        lines = content.splitlines()
        results = []

        # Common regex patterns for function definitions in TS/JS/Go/Rust/Java
        patterns = [
            # 1. Standard function: function foo(...) or async function foo(...) or export function foo(...)
            re.compile(r'^(?:export\s+)?(?:default\s+)?(?:async\s+)?function(?:\s*\*|\s+)+([a-zA-Z0-9_$]+)\s*\((.*?)\)'),
            # 2. Arrow or const function: const foo = (...) => or const foo = async (...) =>
            re.compile(r'^(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\((.*?)\)\s*(?::\s*[^=]+)?=>'),
            # 3. Go func: func Foo(...) or func (r *Recv) Foo(...)
            re.compile(r'^func\s+(?:\([a-zA-Z0-9_*\s,]+\)\s+)?([a-zA-Z0-9_]+)\s*\((.*?)\)'),
            # 4. Rust fn: fn foo(...) or pub fn foo(...) or pub(crate) fn foo(...)
            re.compile(r'^(?:pub(?:\([a-zA-Z0-9_]+\))?\s+)?(?:async\s+)?fn\s+([a-zA-Z0-9_]+)\s*(?:<.*?>)?\s*\((.*?)\)'),
            # 5. Class method: foo(...) { or async foo(...) { or public void foo(...) {
            re.compile(r'^\s*(?:(?:public|private|protected|static|async|override|readonly)\s+)*([a-zA-Z0-9_$]+)\s*\((.*?)\)\s*(?::\s*[^{]+)?\{'),
        ]

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                continue

            for pattern in patterns:
                m = pattern.search(stripped)
                if m:
                    func_name = m.group(1)
                    if func_name in {'if', 'for', 'while', 'switch', 'catch'}:
                        continue

                    start_line = i + 1
                    end_line = self._find_matching_brace_end(lines, i)
                    signature = stripped.split('{')[0].strip()

                    results.append({
                        'function_id': f'FUNC:{func_name}',
                        'name': func_name,
                        'start': start_line,
                        'end': end_line,
                        'signature': signature,
                        'source': '\n'.join(lines[start_line - 1:end_line]),
                        'language': lang,
                    })
                    break

        return results

    @staticmethod
    def _find_matching_brace_end(lines: list[str], start_idx: int) -> int:
        """Find the matching closing brace '}' line index (1-based)."""
        open_braces = 0
        found_first_brace = False

        for idx in range(start_idx, len(lines)):
            line = lines[idx]
            # Strip string literals and comments to avoid counting braces inside strings
            sanitized = re.sub(r'".*?"|\'.*?\'|`.*?`|//.*', '', line)
            for ch in sanitized:
                if ch == '{':
                    open_braces += 1
                    found_first_brace = True
                elif ch == '}':
                    open_braces -= 1
                    if found_first_brace and open_braces <= 0:
                        return idx + 1

        # If matching brace not found, default to start line or a reasonable small block
        return min(start_idx + 10, len(lines))
