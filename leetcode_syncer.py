from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


# Dependencies are installed beside this script so the syncer does not need
# administrator rights or modify the user's system-wide Python installation.
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
LOCAL_RUNTIME = SCRIPT_DIR / ".runtime"
if LOCAL_RUNTIME.is_dir():
    sys.path.insert(0, str(LOCAL_RUNTIME))


CONFIG_PATH = SCRIPT_DIR / "config.json"
REPO: pathlib.Path
EXPECTED_REMOTE: str
GIT_NAME: str
GIT_EMAIL: str
GRAPHQL_URL = "https://leetcode.com/graphql/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36"
LANG_EXT = {
    "bash": "sh", "c": "c", "cpp": "cpp", "csharp": "cs", "dart": "dart",
    "elixir": "ex", "erlang": "erl", "golang": "go", "java": "java",
    "javascript": "js", "kotlin": "kt", "mssql": "sql", "mysql": "sql",
    "oraclesql": "sql", "php": "php", "postgresql": "sql", "python": "py",
    "python3": "py", "racket": "rkt", "ruby": "rb", "rust": "rs",
    "scala": "scala", "swift": "swift", "typescript": "ts",
}


def load_config() -> None:
    """Load non-secret local settings or create them on the first run."""
    global REPO, EXPECTED_REMOTE, GIT_NAME, GIT_EMAIL

    if CONFIG_PATH.is_file():
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    else:
        print("=== FIRST-TIME SETUP ===")
        print("Only non-secret local settings are saved. Login cookies are never stored.")
        repo_path = input("Local path to your LeetCode solutions repository: ").strip().strip('"')
        remote = input("Expected GitHub repository URL: ").strip()
        git_name = input("Git commit author name: ").strip()
        git_email = input("Git commit author email (a GitHub noreply address is recommended): ").strip()
        config = {
            "solutions_repository": repo_path,
            "expected_remote": remote,
            "git_name": git_name,
            "git_email": git_email,
        }
        CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        print(f"Saved local settings to {CONFIG_PATH}")

    required = ("solutions_repository", "expected_remote", "git_name", "git_email")
    missing = [key for key in required if not str(config.get(key, "")).strip()]
    if missing:
        raise RuntimeError(f"Missing configuration values: {', '.join(missing)}")

    REPO = pathlib.Path(config["solutions_repository"]).expanduser().resolve()
    EXPECTED_REMOTE = str(config["expected_remote"]).strip()
    GIT_NAME = str(config["git_name"]).strip()
    GIT_EMAIL = str(config["git_email"]).strip()


def find_chrome() -> pathlib.Path:
    candidates = [
        shutil.which("chrome"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for candidate in candidates:
        if candidate and pathlib.Path(candidate).is_file():
            return pathlib.Path(candidate)
    raise RuntimeError("Google Chrome was not found. Install Chrome and try again.")


def available_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for_chrome(port: int, process: subprocess.Popen, timeout_seconds: int = 30) -> None:
    deadline = time.monotonic() + timeout_seconds
    url = f"http://127.0.0.1:{port}/json/version"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Chrome closed before login was completed.")
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.25)
    raise RuntimeError("Chrome started, but the syncer could not connect to it.")


def get_leetcode_session() -> str:
    """Let the user log in using regular Chrome, then read the session in memory."""
    try:
        from selenium import webdriver
        from selenium.common.exceptions import WebDriverException
    except ImportError as error:
        raise RuntimeError(
            "Selenium is not installed. Run Sync-New-LeetCode.cmd so dependencies are installed."
        ) from error

    profile_dir = pathlib.Path(tempfile.mkdtemp(prefix="leetcode-sync-browser-"))
    chrome = find_chrome()
    port = available_local_port()
    process = None
    driver = None
    try:
        print("A regular Chrome window will open with a temporary profile.")
        print("You may use email, GitHub, Google, or another available login method.")
        process = subprocess.Popen(
            [
                str(chrome),
                f"--remote-debugging-port={port}",
                f"--user-data-dir={profile_dir}",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                "https://leetcode.com/accounts/login/",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        wait_for_chrome(port, process)

        input("Complete the login in Chrome, then return here and press Enter...")
        if process.poll() is not None:
            raise RuntimeError("Chrome was closed before the session could be read.")

        # Attach only after the user finishes authentication. This keeps Google
        # and GitHub sign-in pages out of an automation-controlled browser.
        options = webdriver.ChromeOptions()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
        driver = webdriver.Chrome(options=options)
        driver.get("https://leetcode.com/")
        cookie = driver.get_cookie("LEETCODE_SESSION")
        if not cookie or not cookie.get("value"):
            raise RuntimeError(
                "LeetCode login was not detected. Finish the login before pressing Enter."
            )
        return str(cookie["value"])
    except WebDriverException as error:
        raise RuntimeError(
            "The syncer could not connect to Chrome. Make sure Chrome is up to date."
        ) from error
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        # Chrome can hold profile files briefly after quit; retry the cleanup.
        for _ in range(5):
            shutil.rmtree(profile_dir, ignore_errors=True)
            if not profile_dir.exists():
                break
            time.sleep(0.2)


def run_git(*args: str, capture: bool = False, env: dict | None = None) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={REPO.as_posix()}", "-c", "http.sslBackend=openssl", "-C", str(REPO), *args], check=True, text=True,
        stdout=subprocess.PIPE if capture else None, env=env,
    )
    return result.stdout.strip() if capture else ""


def graphql(cookie: str, payload: dict, retries: int = 5) -> dict:
    headers = {
        "Authorization": f"Bearer {cookie}", "Content-Type": "application/json",
        "Cookie": f"LEETCODE_SESSION={cookie}", "Origin": "https://leetcode.com",
        "Referer": "https://leetcode.com/", "User-Agent": USER_AGENT,
    }
    encoded = json.dumps(payload).encode()
    for attempt in range(retries):
        try:
            request = urllib.request.Request(GRAPHQL_URL, encoded, headers, method="POST")
            with urllib.request.urlopen(request, timeout=45) as response:
                body = json.load(response)
            if body.get("errors"):
                raise RuntimeError(str(body["errors"]))
            return body["data"]
        except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError):
            if attempt + 1 == retries:
                raise
            time.sleep(attempt + 1)
    raise RuntimeError("LeetCode request failed")


def update_readme() -> None:
    counts = {"cpp": 0, "py": 0, "sql": 0}
    solution_paths = list(REPO.glob("*-*/solution.*"))
    for path in solution_paths:
        suffix = path.suffix.removeprefix(".")
        if suffix in counts:
            counts[suffix] += 1
    total = len(solution_paths)
    readme = REPO / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = re.sub(r"solutions-\d+-", f"solutions-{total}-", text)
    text = re.sub(r"C%2B%2B-\d+-", f"C%2B%2B-{counts['cpp']}-", text)
    text = re.sub(r"Python-\d+-", f"Python-{counts['py']}-", text)
    text = re.sub(r"SQL-\d+-", f"SQL-{counts['sql']}-", text)
    text = re.sub(r"\| C\+\+ \| \d+ \|", f"| C++ | {counts['cpp']} |", text)
    text = re.sub(r"\| Python \| \d+ \|", f"| Python | {counts['py']} |", text)
    text = re.sub(r"\| SQL \| \d+ \|", f"| SQL | {counts['sql']} |", text)
    text = re.sub(r"\| \*\*Total\*\* \| \*\*\d+\*\* \|", f"| **Total** | **{total}** |", text)
    readme.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    load_config()
    if not (REPO / ".git").is_dir():
        raise RuntimeError(f"Local repository not found: {REPO}")
    if run_git("remote", "get-url", "origin", capture=True) != EXPECTED_REMOTE:
        raise RuntimeError("Safety stop: origin does not match the expected repository")
    if run_git("status", "--porcelain", capture=True):
        raise RuntimeError("Safety stop: local repository has uncommitted changes")
    run_git("config", "user.name", GIT_NAME)
    run_git("config", "user.email", GIT_EMAIL)

    print("=== LEETCODE LOGIN ===")
    cookie = get_leetcode_session()
    print("Login detected. Starting synchronization...")

    payload = {
        "query": "query userProgressQuestionList($filters: UserProgressQuestionListInput) { userProgressQuestionList(filters: $filters) { questions { frontendId title titleSlug lastSubmittedAt } } }",
        "variables": {"filters": {"questionStatus": "SOLVED", "skip": 0, "limit": 4000}},
        "operationName": "userProgressQuestionList",
    }
    try:
        questions = graphql(cookie, payload)["userProgressQuestionList"]["questions"]
        existing = {p.name.split("-", 1)[1] for p in REPO.iterdir() if p.is_dir() and re.match(r"^\d+-", p.name)}
        pending = sorted((q for q in questions if q["titleSlug"] not in existing), key=lambda q: q["lastSubmittedAt"])
        print(f"New accepted problems: {len(pending)}")

        for index, question in enumerate(pending, 1):
            slug = question["titleSlug"]
            overview = graphql(cookie, {
                "query": "query submissionList($offset: Int!, $limit: Int!, $questionSlug: String!, $status: Int) { questionSubmissionList(offset: $offset, limit: $limit, questionSlug: $questionSlug, status: $status) { submissions { id lang } } }",
                "variables": {"questionSlug": slug, "offset": 0, "limit": 1, "status": 10},
                "operationName": "submissionList",
            })["questionSubmissionList"]["submissions"]
            if not overview:
                print(f"[{index}/{len(pending)}] skipped {slug}")
                continue
            submission = overview[0]
            details = graphql(cookie, {
                "query": "query submissionDetails($submissionId: Int!) { submissionDetails(submissionId: $submissionId) { code } }",
                "variables": {"submissionId": int(submission["id"])},
                "operationName": "submissionDetails",
            })["submissionDetails"]
            if not details or not details.get("code"):
                print(f"[{index}/{len(pending)}] skipped {slug}: code unavailable")
                continue

            folder = REPO / f"{question['frontendId']}-{slug}"
            folder.mkdir()
            extension = LANG_EXT.get(submission["lang"], submission["lang"].replace("/", "_"))
            solution = folder / f"solution.{extension}"
            solution.write_text(details["code"], encoding="utf-8", newline="\n")
            run_git("add", "--", str(solution.relative_to(REPO)))
            commit_env = os.environ.copy()
            commit_env.update({"GIT_AUTHOR_DATE": question["lastSubmittedAt"], "GIT_COMMITTER_DATE": question["lastSubmittedAt"]})
            run_git("commit", "-m", f"Add LeetCode solution: {question['frontendId']} {question['title']}", env=commit_env)
            print(f"[{index}/{len(pending)}] imported {slug}")

        if pending:
            update_readme()
            if run_git("status", "--porcelain", capture=True):
                run_git("add", "--", "README.md")
                run_git("commit", "-m", "Update solution statistics")
        cookie = ""

        ahead = int(run_git("rev-list", "--count", "origin/main..main", capture=True))
        if ahead == 0:
            print("Everything is already synchronized.")
            return 0
        print(f"Ready to push {ahead} new commit(s).")
        if input("Push to GitHub now? [y/N]: ").strip().lower() != "y":
            print("Not pushed. Local commits were kept for review.")
            return 0
        run_git("push", "origin", "main")
        print("Synchronization complete.")
        return 0
    finally:
        cookie = ""


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
