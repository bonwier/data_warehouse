import subprocess
from pathlib import Path


def get_git_context():
    print("=== Recent Codebase Modifications ===")
    try:
        # 1. Show names of files changed but not committed yet
        unstaged = subprocess.check_output(["git", "diff", "--name-only"], text=True)
        if unstaged.strip():
            print(f"Modified/Unstaged Files:\n{unstaged.strip()}\n")

        # 2. Show the summary of the last 3 commits to give the AI immediate historical timeline context
        log = subprocess.check_output(["git", "log", "-n", "3", "--oneline"], text=True)
        print(f"Last 3 Commits:\n{log.strip()}")
    except Exception:
        print("No active git repository tracking found.")
    print("=" * 40)


if __name__ == "__main__":
    get_git_context()
