import re


ENVIRONMENT_ERROR_PATTERNS = [
    r'ModuleNotFoundError: No module named',
    r'ImportError:',
    r'ValueError: negative shift count',
    r'torch\._dynamo',
    r'mpmath',
    r'sympy',
]

SOURCE_BUG_PATTERNS = [
    r'AttributeError:',
    r'TypeError:',
    r'ValueError:',
    r'RuntimeError:',
]

TEST_SYNTAX_PATTERNS = [
    r'SyntaxError:',
    r'IndentationError:',
    r'ast\.parse',
]


def classify_pytest_failure(output, source_file=None, test_file=None):
    text = output or ''
    if any(re.search(pattern, text) for pattern in TEST_SYNTAX_PATTERNS):
        return 'test_quality', 'generated test has syntax/import collection errors'
    if any(re.search(pattern, text) for pattern in ENVIRONMENT_ERROR_PATTERNS):
        return 'environment', 'pytest failed because of dependency/environment errors; replan is unlikely to help'
    normalized_source = (source_file or '').replace('\\', '/')
    if normalized_source and normalized_source in text.replace('\\', '/'):
        if any(re.search(pattern, text) for pattern in SOURCE_BUG_PATTERNS):
            return 'source_or_complex_runtime', f'failure traceback reaches {normalized_source}; rollback and manual review are safer than replanning'
    return 'test_quality', 'failure appears repairable by changing generated tests'


def replanable_failures(verification_results, source_by_target=None):
    source_by_target = source_by_target or {}
    feedback_allowed = {}
    blocked = []
    for result in verification_results or []:
        if result.status not in {'rolled_back', 'proof_rolled_back', 'failed_pending_batch_rollback', 'batch_rolled_back'}:
            continue
        category, reason = classify_pytest_failure(result.output, source_by_target.get(result.target_id), result.test_file)
        if category == 'test_quality':
            feedback_allowed[result.target_id] = reason
        else:
            blocked.append((result.target_id, category, reason))
    return feedback_allowed, blocked
