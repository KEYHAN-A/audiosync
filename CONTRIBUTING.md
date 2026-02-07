# Contributing to AudioSync Pro

Thank you for your interest in contributing! AudioSync Pro is an open-source project and we welcome contributions of all kinds.

## Getting Started

### Prerequisites

- Python 3.10+
- FFmpeg installed and available in your PATH
- Git

### Development Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/KEYHAN-A/audiosync.git
   cd audiosync
   ```

2. **Create a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # macOS/Linux
   # or
   .venv\Scripts\activate     # Windows
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**

   ```bash
   python main.py
   ```

## How to Contribute

### Reporting Bugs

- Use the [GitHub Issues](https://github.com/KEYHAN-A/audiosync/issues) page
- Include steps to reproduce, expected vs actual behavior
- Include your OS version and Python version

### Suggesting Features

- Open an issue with the `enhancement` label
- Describe the use case and why the feature would be useful

### Submitting Code

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Test thoroughly — ensure existing functionality isn't broken
5. Commit with clear messages: `git commit -m "Add feature: description"`
6. Push to your fork: `git push origin feature/your-feature`
7. Open a Pull Request against `main`

### Code Style

- Follow PEP 8 for Python code
- Use type hints where practical
- Keep functions focused and well-documented
- Use docstrings for modules, classes, and public methods

### Project Structure

```
audiosync/
├── main.py              # Application entry point
├── version.py           # Centralized version info
├── core/                # Audio processing engine (no UI)
│   ├── audio_io.py      # File loading, caching, export
│   ├── engine.py        # Analysis and sync algorithms
│   ├── grouping.py      # Auto-group files by device
│   └── models.py        # Data models (Track, Clip, etc.)
├── app/                 # PyQt6 desktop UI
│   ├── main_window.py   # Main window and worker threads
│   ├── track_card.py    # Card-based track list
│   ├── waveform_view.py # Timeline visualization
│   ├── workflow_bar.py  # Step indicator bar
│   ├── dialogs.py       # Processing, export, about dialogs
│   └── theme.py         # Color palette and QSS styles
└── website/             # Landing page (static HTML)
```

## License

By contributing, you agree that your contributions will be licensed under the [GPL v3 License](LICENSE).
