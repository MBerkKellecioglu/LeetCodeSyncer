# LeetCode Syncer

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg)

LeetCode Syncer downloads your newly accepted LeetCode submissions, records them in a local Git repository, and optionally pushes the resulting commits to GitHub.

No session cookie needs to be copied or pasted. The application opens a temporary, regular Chrome profile so you can sign in with any method supported by LeetCode, including email, GitHub, and Google.

## Highlights

- Opens regular Chrome for interactive authentication.
- Attaches browser automation only after authentication is complete.
- Keeps the `LEETCODE_SESSION` value in memory and never writes it to configuration.
- Uses a separate temporary Chrome profile instead of reading your everyday browser profile.
- Imports only accepted problems that are not already present locally.
- Saves the latest accepted submission for each new problem.
- Creates one Git commit per solution and preserves its LeetCode submission timestamp.
- Updates existing solution statistics in the solutions repository README.
- Verifies the configured Git remote before making changes.
- Stops when the solutions repository contains uncommitted changes.
- Asks for confirmation before pushing commits to GitHub.

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or newer
- Google Chrome
- Git
- An existing local clone of your LeetCode solutions repository

## Quick Start

1. Clone or download this repository.
2. Double-click [`run.bat`](run.bat).
3. Complete the first-time setup:
   - Enter the local path to your solutions repository.
   - Enter its expected GitHub remote URL.
   - Enter your Git commit author name and email.
4. Sign in to LeetCode in the Chrome window that opens.
5. Return to the terminal and press `Enter` after LeetCode confirms the login.
6. Review the generated commits and approve the optional GitHub push.

The launcher installs Selenium into the project's private `.runtime` directory. It does not require administrator access and does not modify the system-wide Python installation.

## Configuration

Non-secret settings are stored locally in `config.json` after the first run. This file is ignored by Git.

```json
{
  "solutions_repository": "C:\\path\\to\\your\\leetcode-solutions",
  "expected_remote": "https://github.com/your-name/leetcode-solutions.git",
  "git_name": "Your Name",
  "git_email": "12345678+your-name@users.noreply.github.com"
}
```

To change the setup, edit or delete `config.json`. A template is available in [`config.example.json`](config.example.json).

## Security Model

The authentication flow is intentionally designed to minimize credential exposure:

1. Chrome starts with a new temporary profile.
2. You complete authentication directly on the LeetCode, GitHub, or Google pages.
3. The program connects to Chrome only after you press `Enter`.
4. The LeetCode session cookie is copied into process memory for API requests.
5. Chrome closes and the temporary profile is removed.
6. The cookie is never printed, committed, or written to `config.json`.

The syncer does not read cookies from your regular Chrome profile and never asks for your LeetCode password.

## Repository Layout

```text
LeetCodeSyncer/
├── leetcode_syncer.py   # Authentication, download, commit, and push workflow
├── run.bat              # Windows launcher and local dependency setup
├── requirements.txt     # Python dependencies
├── config.example.json  # Non-secret configuration template
├── tests/               # Local unit tests
├── LICENSE
└── README.md
```

## How Synchronization Works

1. The syncer validates the local Git repository, configured remote, and working tree.
2. It opens Chrome and waits for you to finish signing in.
3. It requests the list of solved LeetCode problems.
4. It compares problem slugs with the local solution directories.
5. For each missing problem, it downloads the latest accepted submission.
6. It saves the source file and creates a timestamped Git commit.
7. It updates supported statistics in the solutions repository README.
8. It asks before pushing any new commits.

## Troubleshooting

### Google says the browser may not be secure

Make sure you are using the current version of the syncer. Authentication must happen before the program attaches Selenium to Chrome. Close any older sync window and start the application again with `run.bat`.

### Selenium cannot be loaded

Delete the local `.runtime` directory and run `run.bat` again. The launcher will reinstall the dependency locally.

### The remote safety check fails

Compare this command's output with `expected_remote` in `config.json`:

```powershell
git -C "C:\path\to\your\leetcode-solutions" remote get-url origin
```

The values must match exactly.

### LeetCode changes its API

LeetCode does not publish a stable public API for this workflow. A site-side GraphQL change may require an update to the syncer.

## Privacy

Your source code is written only to the solutions repository you configure. Nothing is uploaded until you approve the Git push prompt.

## License

This project is available under the [MIT License](LICENSE).
