"""Read actual trial files and check the rules; does not generate weekly outputs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADINGS = ['## 本周完成', '## 下周计划', '## 待协调', '## 需确认']


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_trial(source_name, output_name):
    source, output = ROOT / source_name, ROOT / output_name
    expected = [[] for _ in HEADINGS]
    for line in source.read_text().splitlines():
        if not line.strip() or line.startswith('[internal]'):
            continue
        for prefix, index in (('[done]', 0), ('[next]', 1), ('[blocked]', 2)):
            if line.startswith(prefix):
                expected[index].append('- ' + line[len(prefix):].lstrip(' '))
                break
        else:
            expected[3].append('- ' + line)

    lines = output.read_text().splitlines()
    assert lines[0] == '# 团队周报', output_name
    assert lines[-1] == '状态：草稿', output_name
    assert [line for line in lines if line.startswith('#')] == ['# 团队周报', *HEADINGS], output_name
    assert all(not line.strip() for line in lines[1:lines.index(HEADINGS[0])]), output_name
    for index, heading in enumerate(HEADINGS):
        start = lines.index(heading) + 1
        stop = lines.index(HEADINGS[index + 1]) if index < 3 else len(lines) - 1
        actual = [line for line in lines[start:stop] if line.strip()]
        assert actual == (expected[index] or ['无']), (output_name, heading, actual, expected[index])
    return {'input': source_name, 'output': output_name, 'passed': True,
            'section_item_counts': [len(items) for items in expected],
            'input_sha256': fingerprint(source), 'output_sha256': fingerprint(output)}


before = json.loads((ROOT / 'checks/input-before.json').read_text())
unchanged = {name: fingerprint(ROOT / name) == digest for name, digest in before.items()}
assert all(unchanged.values()), unchanged
trials = [check_trial(*pair) for pair in [
    ('sample.md', 'weekly.md'),
    ('checks/boundary-input.md', 'checks/boundary-weekly.md'),
    ('checks/internal-only-input.md', 'checks/internal-only-weekly.md'),
]]
print(json.dumps({'inputs_unchanged': unchanged, 'trials': trials,
    'scope': 'Actual file structure and source-to-output comparison; not host registration or human acceptance.'},
    ensure_ascii=False, indent=2))
