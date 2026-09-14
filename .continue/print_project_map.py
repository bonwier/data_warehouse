import sys
from pathlib import Path

# Initialize project roots based on your environment
SCRIPT_DIR = (
    Path(__file__).resolve().parent if "__file__" in locals() else Path(".").resolve()
)
PROJECT_ROOT = SCRIPT_DIR
while PROJECT_ROOT.name != "data_warehouse" and PROJECT_ROOT.parent != PROJECT_ROOT:
    PROJECT_ROOT = PROJECT_ROOT.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configuration sets for ignored items
IGNORE_DIRS = {
    ".venv",
    ".continue",
    ".git",
    "__pycache__",
    ".idea",
    ".vscode",
    "2025.annual.by_area",
}
IGNORE_FILES = {
    ".DS_Store",
    "thumbs.db",
    ".gitignore",
    "directory_map.txt",
    ".continueignore",
}


def build_tree_lines(dir_path: Path, prefix: str = "") -> list[str]:
    """Recursively builds lines for a visual directory tree, skipping ignored items."""
    lines = []
    if not dir_path.is_dir():
        return lines

    try:
        # Filter and sort contents (folders first, then files)
        contents = sorted(
            [
                p
                for p in dir_path.iterdir()
                if not (p.is_dir() and p.name in IGNORE_DIRS)
                and not (p.is_file() and p.name in IGNORE_FILES)
            ],
            key=lambda s: (s.is_file(), s.name.lower()),
        )
    except PermissionError:
        return lines

    count = len(contents)
    for index, path in enumerate(contents):
        is_last = index == count - 1
        connector = "└── " if is_last else "├── "

        # Append current item line
        lines.append(f"{prefix}{connector}{path.name}")

        # Recurse into subdirectories
        if path.is_dir():
            next_prefix = f"{prefix}    " if is_last else f"{prefix}│   "
            lines.extend(build_tree_lines(path, next_prefix))

    return lines


if __name__ == "__main__":
    # Define output destination
    output_dir = PROJECT_ROOT / ".continue"
    output_file = output_dir / "directory_map.txt"

    # Ensure the .continue directory exists
    output_dir.mkdir(exist_ok=True)

    # Generate tree content
    tree_output = [f"Project Tree for: {PROJECT_ROOT.name} ({PROJECT_ROOT})"]
    tree_output.extend(build_tree_lines(PROJECT_ROOT))

    # Write output to file
    try:
        output_file.write_text("\n".join(tree_output) + "\n", encoding="utf-8")
        print(f"Success! Directory map saved to: {output_file}")
    except Exception as e:
        print(f"Error writing file: {e}", file=sys.stderr)
