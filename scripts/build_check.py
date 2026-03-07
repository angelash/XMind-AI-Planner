from pathlib import Path
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]

    compile_cmd = [sys.executable, "-m", "compileall", "-q", "backend", "tests"]
    test_cmd = [sys.executable, "-m", "pytest", "-q"]

    if subprocess.run(compile_cmd, cwd=root).returncode != 0:
        return 1
    if subprocess.run(test_cmd, cwd=root).returncode != 0:
        return 1

    required = [
        root / "frontend" / "index.html",
        root / "frontend" / "src" / "main.js",
        root / "backend" / "app" / "main.py",
    ]
    for path in required:
        if not path.exists():
            print(f"missing required file: {path}")
            return 1

    print("build_check_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
