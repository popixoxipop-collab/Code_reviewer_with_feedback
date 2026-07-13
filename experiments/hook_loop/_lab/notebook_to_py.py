"""LLMOps pilot -- .ipynb -> scannable .py 전처리.

cognition/two_tier_scan.py의 Python 경로(extract_py_targets)는 정규식 기반이라
AST 파싱을 안 한다 -- 그래서 Colab 매직(`!pip install`, `%env` 등)이 섞여도 크래시하지
않는다. 이 스크립트는 순전히 가독성/추적성을 위해 코드 셀만 이어붙이고, 마크다운 셀은
위치추적용 주석으로, 셸 이스케이프(`!`)/라인매직(`%`)은 주석 처리한다 -- `%%writefile X`
같은 셀매직은 첫 줄만 주석 처리하고 나머지(실제로 X에 쓰이는 진짜 코드)는 그대로 둔다.

Usage:
  python3 experiments/hook_loop/_lab/notebook_to_py.py <in.ipynb> <out.py>
"""
import json
import re
import sys
from pathlib import Path

CELL_MAGIC_PREFIXES = ("%%",)
LINE_MAGIC_OR_SHELL_PREFIXES = ("!", "%")
_BASE64_IMAGE_RE = re.compile(r"data:image/[a-zA-Z]+;base64,[A-Za-z0-9+/=]{100,}")


def convert_cell_source(cell_type, source_lines):
    src = "".join(source_lines)
    if cell_type == "markdown":
        src = _BASE64_IMAGE_RE.sub("[image data omitted]", src)
        commented = "\n".join(f"# {line}" for line in src.splitlines())
        return f"# --- markdown ---\n{commented}\n"
    if cell_type != "code":
        return ""
    lines = src.splitlines()
    out = []
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if i == 0 and stripped.startswith(CELL_MAGIC_PREFIXES):
            out.append(f"# [cell-magic] {line}")
        elif stripped.startswith(LINE_MAGIC_OR_SHELL_PREFIXES) and not stripped.startswith("#"):
            out.append(f"# [magic] {line}")
        else:
            out.append(line)
    return "\n".join(out) + "\n"


def convert(in_path, out_path):
    nb = json.loads(Path(in_path).read_text(encoding="utf-8"))
    chunks = [f"# source notebook: {Path(in_path).name}\n"]
    for i, cell in enumerate(nb.get("cells", [])):
        piece = convert_cell_source(cell.get("cell_type"), cell.get("source", []))
        if piece.strip():
            chunks.append(f"# --- cell {i} ---\n{piece}")
    Path(out_path).write_text("\n".join(chunks), encoding="utf-8")
    return len(nb.get("cells", []))


if __name__ == "__main__":
    n = convert(sys.argv[1], sys.argv[2])
    print(f"[notebook_to_py] {sys.argv[1]} ({n} cells) -> {sys.argv[2]}", file=sys.stderr)
