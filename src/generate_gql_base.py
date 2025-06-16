import ast
import argparse
import sys
import subprocess
from pathlib import Path

# List of valid basic data types
BASIC_TYPES = {
    "UUID",
    "str",
    "int",
    "float",
    "bool",
    "datetime",
    "Decimal",
    "date",
    "datetime_date",
}


def is_basic_type(field_type: str) -> bool:
    """
    Check if the data type is included in the valid basic types.
    """
    if field_type.startswith("Optional["):
        inner_type = field_type[9:-1]
    else:
        inner_type = field_type
    return inner_type in BASIC_TYPES


def extract_models_from_file(file_path: Path):
    """
    Extract models from a Python file and get basic fields.
    """
    with file_path.open("r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    models = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            model_name = node.name
            fields = []
            for item in node.body:
                if isinstance(item, ast.AnnAssign):
                    # Ignore Relationship
                    val = item.value
                    if (
                        isinstance(val, ast.Call)
                        and isinstance(val.func, ast.Name)
                        and val.func.id == "Relationship"
                    ):
                        continue
                    # Field name
                    target = item.target
                    field_name = target.id if isinstance(target, ast.Name) else None
                    # Data type
                    annot = item.annotation
                    field_type = "Any"
                    if isinstance(annot, ast.Subscript) and isinstance(
                        annot.value, ast.Name
                    ):
                        outer = annot.value.id
                        sl = annot.slice
                        if isinstance(sl, ast.Name):
                            inner = sl.id
                        elif isinstance(sl, ast.Constant):
                            inner = sl.value
                        else:
                            inner = None
                        if outer and inner:
                            field_type = f"{outer}[{inner}]"
                    elif isinstance(annot, ast.Name):
                        field_type = annot.id
                    # Special for bytes
                    if field_type == "bytes":
                        fields.append((field_name, "Optional[bytes]"))
                    # Ignore if not a basic type
                    if not is_basic_type(field_type):
                        continue
                    # Change date to datetime_date
                    if "date" in field_type and "datetime" not in field_type:
                        field_type = field_type.replace("date", "datetime_date")
                    fields.append((field_name, field_type))
            if fields:
                models.append((model_name, fields))
    return models


def generate_dataclasses(models, output_file: Path, sort_fields: bool):
    """
    Generate dataclasses to the output file.
    """
    header = (
        "from decimal import Decimal\n"
        "from typing import Optional\n"
        "from uuid import UUID\n"
        "from datetime import datetime, date as datetime_date\n"
        "from dataclasses import dataclass\n"
        "from base.gql.schema import BaseDataModel\n\n"
    )
    body = ""
    for name, fields in models:
        if sort_fields:
            fields.sort(key=lambda x: x[0] or "")
        body += f"@dataclass\nclass Base{name}(BaseDataModel):\n"
        for fname, ftype in fields:
            body += f"    {fname}: {ftype} = None\n"
        body += "\n"

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as f:
        f.write(header + body)
    print(f"✔ File {output_file} created.")


def format_code(path: Path):
    """
    Format Python code in the given file using Black.
    """
    try:
        subprocess.run(
            [sys.executable, "-m", "black", "--quiet", str(path)], check=True
        )
    except subprocess.CalledProcessError:
        pass


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate base schemas from app/<app_name>/models.py or all apps "
            "if no argument is given"
        )
    )
    parser.add_argument(
        "app",
        nargs="?",
        help="App name in the app/ folder. If not provided, process all apps.",
    )
    parser.add_argument(
        "--sort", action="store_true", help="Sort fields alphabetically"
    )
    args = parser.parse_args()

    script_dir = Path(__file__).parent.resolve()
    app_root = script_dir / "app"
    if not app_root.exists():
        print(f"❗ Folder app/ not found on {app_root}")
        sys.exit(1)

    # Determine app paths to process
    if args.app:
        roots = [app_root / args.app]
    else:
        roots = [
            p for p in app_root.iterdir() if p.is_dir() and p.name != "__pycache__"
        ]

    for root in roots:
        if not root.exists():
            print(f"❗ App '{root.name}' not found, skipped.")
            continue

        # Collect all models.py at the direct level and one level below
        model_paths = []
        direct = root / "models.py"
        if direct.exists():
            model_paths.append(direct)
        # Search nested one level below
        for sub in root.iterdir():
            if sub.is_dir() and sub.name != "__pycache__":
                nested = sub / "models.py"
                if nested.exists():
                    model_paths.append(nested)

        if not model_paths:
            print(f"❗ models.py not found on app '{root.name}', skipped.")
            continue

        # Process each found models.py
        for models_file in model_paths:
            app_path = models_file.parent
            schema_dir = app_path / "schemas"
            base_file = schema_dir / "base.py"
            schema_dir.mkdir(parents=True, exist_ok=True)
            (schema_dir / "__init__.py").touch(exist_ok=True)

            models = extract_models_from_file(models_file)
            if not models:
                print(f"⚠  No valid model on '{app_path.name}'.")
                continue

            generate_dataclasses(models, base_file, sort_fields=args.sort)
            format_code(base_file)


if __name__ == "__main__":
    main()
