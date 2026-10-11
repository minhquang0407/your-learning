import json
import re
from dataclasses import dataclass, field


@dataclass
class LLMGeneratedTest:
    test_file: str
    test_names: list
    code: str
    rationale: str
    assumptions: list = field(default_factory=list)
    requires: list = field(default_factory=list)


UNSAFE_CODE_PATTERNS = [
    r'\bsubprocess\b',
    r'\bos\.system\b',
    r'\bshutil\.rmtree\b',
    r'\brequests\.',
    r'\burllib\.',
    r'\bsocket\b',
    r'open\([^\n]*(?:\.py|requirements|pyproject|setup\.py)',
]


def extract_json_object(text):
    text = (text or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or end < start:
        raise ValueError('LLM response did not contain a JSON object')
    return json.loads(text[start:end + 1])


def parse_generated_test(text):
    data = extract_json_object(text)
    required = ['test_file', 'test_names', 'code', 'rationale']
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f'LLM response missing required keys: {", ".join(missing)}')
    generated = LLMGeneratedTest(
        test_file=str(data['test_file']),
        test_names=list(data['test_names']),
        code=str(data['code']),
        rationale=str(data['rationale']),
        assumptions=list(data.get('assumptions', [])),
        requires=list(data.get('requires', [])),
    )
    validate_generated_test(generated)
    return generated


def parse_repair_response(text):
    data = extract_json_object(text)
    action = data.get('action')
    code = data.get('code')
    if action != 'replace_generated_block':
        raise ValueError('Repair response action must be replace_generated_block')
    if not isinstance(code, str) or not code.strip():
        raise ValueError('Repair response code must be a non-empty string')
    temp = LLMGeneratedTest(
        test_file='tests/generated_repair.py',
        test_names=re.findall(r'^def (test_[a-zA-Z0-9_]+)\(', code, flags=re.MULTILINE),
        code=code,
        rationale=str(data.get('explanation', 'LLM repair')),
    )
    validate_generated_test(temp)
    return code, str(data.get('explanation', 'LLM repair'))


def validate_generated_test(generated: LLMGeneratedTest):
    normalized = generated.test_file.replace('\\', '/')
    if not normalized.startswith('tests/'):
        raise ValueError('test_file must be under tests/')
    if '..' in normalized.split('/'):
        raise ValueError('test_file must not contain parent-directory traversal')
    if not normalized.endswith('.py'):
        raise ValueError('test_file must be a Python file')
    if not generated.test_names:
        raise ValueError('test_names must contain at least one test function')
    actual_names = re.findall(r'^def (test_[a-zA-Z0-9_]+)\(', generated.code, flags=re.MULTILINE)
    if not actual_names:
        raise ValueError('code must define at least one pytest test function')
    missing = [name for name in generated.test_names if name not in actual_names]
    if missing:
        raise ValueError(f'test_names not found in code: {", ".join(missing)}')
    for pattern in UNSAFE_CODE_PATTERNS:
        if re.search(pattern, generated.code):
            raise ValueError(f'code contains unsafe pattern: {pattern}')
    return True
