from pathlib import Path

_PARTS_DIR = Path(__file__).resolve().parent / 'app_parts'
for _name in ('part0.py','part1.py','part2.py','part3.py','part4.py','part5.py','part6.py'):
    _path = _PARTS_DIR / _name
    exec(compile(_path.read_text(encoding='utf-8'), str(_path), 'exec'), globals(), globals())
