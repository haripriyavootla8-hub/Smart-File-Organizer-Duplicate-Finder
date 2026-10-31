# Smart File Organizer & Duplicate Finder

## Project Description
Smart File Organizer & Duplicate Finder is a Python-based desktop application that helps users organize files into different folders and identify duplicate files using SHA-256 hashing.

## Features
- Select a folder.
- Scan files and see counts and sizes by category and extension.
- Organize files into Images, Documents, Spreadsheets, Presentations, Videos, Audio, Archives, Code, and Others.
- Name clashes are handled automatically (e.g. `photo (1).jpg`), and the last organize can be undone.
- Detect duplicate files using SHA-256 hashing (only same-size files are hashed, so it's fast).
- Delete selected duplicate files while keeping the original, with reclaimable space shown.
- Long tasks run in the background with a progress bar, so the window never freezes.

## Technologies Used
- Python
- Tkinter
- SHA-256 Hashing
- Git & GitHub

## Requirements
- Python 3.x
- Windows / Python-supported operating system

## How to Run

1. Clone the repository.
2. Open the project folder in VS Code.
3. Run:

```bash
py main.py
```

## Project Repository
https://github.com/haripriyavootla8-hub/Smart-File-Organizer-Duplicate-Finder

## Author
Hari Priya

GitHub: https://github.com/haripriyavootla8-hub
