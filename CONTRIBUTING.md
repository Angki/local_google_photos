# Contributing to Google Photos Local Takeout Gallery

Thank you for your interest in contributing to **Google Photos Local Takeout Gallery**! We welcome bug fixes, documentation improvements, performance optimizations, and feature enhancements from the community.

---

## 🧭 Code of Conduct

Please review and adhere to our [Code of Conduct](CODE_OF_CONDUCT.md) in all project interactions.

---

## 🛠️ Development Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/local_google_photos.git
   cd local_google_photos
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   
   # Windows
   .venv\Scripts\activate
   
   # Linux / macOS
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Copy `.env.example` to `.env`:**
   ```bash
   cp .env.example .env
   ```
   Configure `TAKEOUT_DIR` to point to a test folder or small sample Takeout archive.

---

## 🧪 Running Tests & Quality Checks

Before submitting a Pull Request, ensure the entire test suite passes:

```bash
# Run unit tests
python -m unittest discover -s tests
```

To run linting locally:
```bash
pip install ruff
ruff check .
```

---

## 🔀 Pull Request Process

1. **Create a feature branch:**
   ```bash
   git checkout -b feat/your-feature-name
   # or for bugfixes
   git checkout -b fix/issue-description
   ```

2. **Commit your changes:**
   - Write clear, concise, and descriptive commit messages using Conventional Commits (`feat:`, `fix:`, `docs:`, `perf:`, `refactor:`).
   - Never commit local media files, personal databases, or credentials.

3. **Submit the PR:**
   - Open a Pull Request targeting the `main` branch.
   - Fill out the PR template completely with screenshots/recordings if modifying the UI.
   - Verify that all GitHub Actions CI checks pass.

---

## 📜 Coding Guidelines

- **Zero Cloud Leakage**: Ensure that all features remain 100% offline and local. Never send user photos, metadata, or embeddings to third-party cloud services.
- **Python Style**: Adhere to PEP 8. Use typing annotations (`Optional`, `List`, `Dict`) where applicable.
- **Pydantic Models**: Ensure every new API route defines explicit Pydantic request and response schemas.
- **Frontend**: Keep frontend lightweight, responsive, and compatible across modern Chromium, Firefox, and Safari browsers.
