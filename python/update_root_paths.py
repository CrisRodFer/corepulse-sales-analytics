from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
PYTHON_DIR = PROJECT_DIR / "python"

OLD_PATTERN = "ROOT_DIR = Path("
NEW_BLOCK = """ROOT_DIR = Path(__file__).resolve().parents[1]"""

for file in PYTHON_DIR.glob("*.py"):
    if file.name == "update_root_paths.py":
        continue

    text = file.read_text(encoding="utf-8")

    if "ROOT_DIR = Path(" in text:
        start = text.find("ROOT_DIR = Path(")
        end = text.find(")", start) + 1

        new_text = text[:start] + NEW_BLOCK + text[end:]

        file.write_text(new_text, encoding="utf-8")
        print(f"✔ Actualizado: {file.name}")
    else:
        print(f"- No encontrado en: {file.name}")