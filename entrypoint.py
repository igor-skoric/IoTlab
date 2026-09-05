import os
import subprocess
import sys


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: entrypoint.py <command> [args...]\n")
        sys.exit(1)

    subprocess.check_call([sys.executable, "manage.py", "collectstatic", "--noinput"])
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
