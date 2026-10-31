"""Smart File Organizer & Duplicate Finder."""

import hashlib
import queue
import shutil
import threading
import tkinter as tk
from collections import Counter, defaultdict
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

FILE_TYPES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic", ".tiff", ".ico"},
    "Documents": {".txt", ".pdf", ".doc", ".docx", ".odt", ".rtf", ".md"},
    "Spreadsheets": {".xls", ".xlsx", ".ods", ".csv"},
    "Presentations": {".ppt", ".pptx", ".odp"},
    "Videos": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"},
    "Audio": {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".json", ".xml"},
}
OTHERS = "Others"
CATEGORY_NAMES = set(FILE_TYPES) | {OTHERS}
CHUNK_SIZE = 1024 * 1024

BG = "#f4f6f9"
TEXT = "#2c3e50"


# Helpers

def category_for(path):
    extension = path.suffix.lower()
    for name, extensions in FILE_TYPES.items():
        if extension in extensions:
            return name
    return OTHERS


def iter_files(folder):
    for item in folder.rglob("*"):
        try:
            if item.is_file():
                yield item
        except OSError:
            continue


def unique_destination(destination):
    """Return a path that doesn't exist yet, e.g. 'photo (1).jpg'."""
    if not destination.exists():
        return destination

    counter = 1
    while True:
        candidate = destination.with_name(
            f"{destination.stem} ({counter}){destination.suffix}"
        )
        if not candidate.exists():
            return candidate
        counter += 1


def file_hash(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def human_size(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


class App:
    def __init__(self, root):
        self.root = root
        self.folder = None
        self.duplicates = {}   # tree item id -> (duplicate path, size)
        self.last_moves = []   # (original path, new path) from last organize
        self.events = queue.Queue()

        self._build_ui()
        self.root.after(100, self._poll_events)

    # UI

    def _build_ui(self):
        self.root.title("Smart File Organizer & Duplicate Finder")
        self.root.geometry("820x700")
        self.root.minsize(700, 600)
        self.root.configure(bg=BG)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Heading.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Status.TLabel", background="#ecf0f1", font=("Segoe UI", 10, "bold"))
        for name, color in (("Blue", "#3498db"), ("Green", "#2ecc71"),
                            ("Purple", "#9b59b6"), ("Red", "#e74c3c"),
                            ("Gray", "#7f8c8d")):
            style.configure(f"{name}.TButton", background=color, foreground="white",
                            font=("Segoe UI", 10, "bold"), padding=(10, 5))
            style.map(f"{name}.TButton", background=[("disabled", "#bdc3c7")])

        ttk.Label(self.root, text="📁 Smart File Organizer & Duplicate Finder",
                  style="Title.TLabel").pack(pady=(15, 10))

        # Folder picker
        folder_frame = ttk.Frame(self.root)
        folder_frame.pack(fill="x", padx=15)
        self.choose_btn = ttk.Button(folder_frame, text="📂 Choose Folder",
                                     style="Blue.TButton", command=self.choose_folder)
        self.choose_btn.pack(side="left")
        self.folder_label = ttk.Label(folder_frame, text="No folder selected",
                                      foreground="#555555")
        self.folder_label.pack(side="left", padx=10, fill="x", expand=True)

        # Actions
        action_frame = ttk.Frame(self.root)
        action_frame.pack(pady=10)
        self.scan_btn = ttk.Button(action_frame, text="🔍 Scan Files",
                                   style="Blue.TButton", command=self.scan_files)
        self.organize_btn = ttk.Button(action_frame, text="📁 Organize Files",
                                       style="Green.TButton", command=self.organize_files)
        self.undo_btn = ttk.Button(action_frame, text="↩ Undo Organize",
                                   style="Gray.TButton", command=self.undo_organize)
        self.duplicate_btn = ttk.Button(action_frame, text="🧩 Find Duplicates",
                                        style="Purple.TButton", command=self.find_duplicates)
        for button in (self.scan_btn, self.organize_btn, self.undo_btn, self.duplicate_btn):
            button.pack(side="left", padx=6)
        self.undo_btn.state(["disabled"])

        # Duplicates table
        ttk.Label(self.root, text="🧩 Duplicate Files",
                  style="Heading.TLabel").pack(anchor="w", padx=15)
        tree_frame = ttk.Frame(self.root)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=5)

        columns = ("duplicate", "original", "size")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                 height=8, selectmode="extended")
        self.tree.heading("duplicate", text="Duplicate")
        self.tree.heading("original", text="Original (kept)")
        self.tree.heading("size", text="Size")
        self.tree.column("duplicate", width=330)
        self.tree.column("original", width=330)
        self.tree.column("size", width=90, anchor="e")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        dup_buttons = ttk.Frame(self.root)
        dup_buttons.pack(fill="x", padx=15)
        self.select_all_btn = ttk.Button(dup_buttons, text="Select All",
                                         style="Gray.TButton", command=self.select_all_duplicates)
        self.delete_btn = ttk.Button(dup_buttons, text="🗑 Delete Selected Duplicates",
                                     style="Red.TButton", command=self.delete_selected_duplicates)
        self.select_all_btn.pack(side="left")
        self.delete_btn.pack(side="left", padx=6)

        # Scan results
        ttk.Label(self.root, text="📊 Scan Results",
                  style="Heading.TLabel").pack(anchor="w", padx=15, pady=(10, 0))
        output_frame = ttk.Frame(self.root)
        output_frame.pack(fill="both", expand=True, padx=15, pady=5)
        self.output = tk.Text(output_frame, height=8, font=("Consolas", 10),
                              bd=1, relief="solid", state="disabled")
        output_scroll = ttk.Scrollbar(output_frame, orient="vertical",
                                      command=self.output.yview)
        self.output.configure(yscrollcommand=output_scroll.set)
        self.output.pack(side="left", fill="both", expand=True)
        output_scroll.pack(side="right", fill="y")

        # Status bar
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", side="bottom")
        self.progress = ttk.Progressbar(status_frame, length=200, mode="determinate")
        self.progress.pack(side="right", padx=10, pady=5)
        self.status_label = ttk.Label(status_frame, text="✅ Ready",
                                      style="Status.TLabel", anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True, padx=10, pady=5)

        self.action_buttons = (self.choose_btn, self.scan_btn, self.organize_btn,
                               self.duplicate_btn, self.select_all_btn, self.delete_btn)

    def set_status(self, text):
        self.status_label.config(text=text)

    def write_output(self, text):
        self.output.config(state="normal")
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, text)
        self.output.config(state="disabled")

    def clear_duplicates(self):
        self.tree.delete(*self.tree.get_children())
        self.duplicates.clear()

    def require_folder(self):
        if self.folder is None:
            messagebox.showwarning("Warning", "Select a folder first!")
            return False
        return True

    # Background tasks

    def _poll_events(self):
        try:
            while True:
                self.events.get_nowait()()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _report_progress(self, done, total):
        def update():
            self.progress.config(maximum=max(total, 1), value=done)
        self.events.put(update)

    def _set_busy(self, busy):
        for button in self.action_buttons:
            button.state(["disabled"] if busy else ["!disabled"])
        if busy or not self.last_moves:
            self.undo_btn.state(["disabled"])
        else:
            self.undo_btn.state(["!disabled"])
        self.root.config(cursor="watch" if busy else "")
        if not busy:
            self.progress.config(value=0)

    def run_task(self, message, work, on_done):
        """Run work(progress) in a thread, then on_done(result) on the UI thread."""
        self._set_busy(True)
        self.set_status(message)

        def runner():
            try:
                result = work(self._report_progress)
            except Exception as error:  # noqa: BLE001 - surfaced to the user
                self.events.put(lambda err=error: self._task_failed(err))
            else:
                self.events.put(lambda: self._task_done(on_done, result))

        threading.Thread(target=runner, daemon=True).start()

    def _task_done(self, on_done, result):
        self._set_busy(False)
        on_done(result)

    def _task_failed(self, error):
        self._set_busy(False)
        self.set_status("❌ Something went wrong")
        messagebox.showerror("Error", str(error))

    # Choose Folder

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Select a folder")
        if not folder:
            return

        self.folder = Path(folder)
        self.folder_label.config(text=str(self.folder))
        self.last_moves = []
        self.undo_btn.state(["disabled"])
        self.write_output("")
        self.clear_duplicates()
        self.set_status("Folder selected")

    # Scan Files

    def scan_files(self):
        if not self.require_folder():
            return
        self.run_task("🔍 Scanning...", self._scan_work, self._scan_done)

    def _scan_work(self, progress):
        counts = Counter()
        sizes = Counter()
        categories = Counter()

        for item in iter_files(self.folder):
            extension = item.suffix.lower() or "(no extension)"
            counts[extension] += 1
            categories[category_for(item)] += 1
            try:
                sizes[extension] += item.stat().st_size
            except OSError:
                pass

        return counts, sizes, categories

    def _scan_done(self, result):
        counts, sizes, categories = result
        total = sum(counts.values())
        total_size = sum(sizes.values())

        lines = [f"Total files: {total}   Total size: {human_size(total_size)}", ""]
        lines.append("By category:")
        for name, count in categories.most_common():
            lines.append(f"  {name:<15}{count:>6} file(s)")
        lines.append("")
        lines.append("By extension:")
        for extension, count in sorted(counts.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {extension:<15}{count:>6} file(s)   {human_size(sizes[extension]):>10}")

        self.write_output("\n".join(lines))
        self.set_status(f"✅ Scan completed: {total} files")

    # Organize Files

    def organize_files(self):
        if not self.require_folder():
            return
        if not messagebox.askyesno(
            "Confirm Organize",
            f"Move all files in\n{self.folder}\ninto category folders?\n\n"
            "You can undo this afterwards."
        ):
            return
        self.run_task("📁 Organizing...", self._organize_work, self._organize_done)

    def _organize_work(self, progress):
        files = [
            item for item in iter_files(self.folder)
            # Skip files already inside category folders
            if item.relative_to(self.folder).parts[0] not in CATEGORY_NAMES
        ]

        moves = []
        errors = []
        for index, item in enumerate(files, 1):
            destination_folder = self.folder / category_for(item)
            try:
                destination_folder.mkdir(exist_ok=True)
                destination = unique_destination(destination_folder / item.name)
                shutil.move(str(item), str(destination))
                moves.append((item, destination))
            except OSError as error:
                errors.append(f"{item.name}: {error}")
            progress(index, len(files))

        return moves, errors

    def _organize_done(self, result):
        moves, errors = result
        if moves:
            self.last_moves = moves
            self.undo_btn.state(["!disabled"])
        self.clear_duplicates()
        self.set_status(f"✅ Organized: {len(moves)} files")

        message = f"{len(moves)} files organized successfully!"
        if errors:
            message += f"\n\n{len(errors)} file(s) could not be moved:\n" + "\n".join(errors[:10])
            messagebox.showwarning("Completed with errors", message)
        else:
            messagebox.showinfo("Completed", message)

    def undo_organize(self):
        if not self.last_moves:
            return
        if not messagebox.askyesno(
            "Confirm Undo",
            f"Move {len(self.last_moves)} file(s) back to where they were?"
        ):
            return
        self.run_task("↩ Undoing...", self._undo_work, self._undo_done)

    def _undo_work(self, progress):
        restored = 0
        errors = []
        for index, (original, moved) in enumerate(self.last_moves, 1):
            try:
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(moved), str(unique_destination(original)))
                restored += 1
            except OSError as error:
                errors.append(f"{moved.name}: {error}")
            progress(index, len(self.last_moves))

        # Remove category folders left empty by the undo
        for name in CATEGORY_NAMES:
            folder = self.folder / name
            try:
                if folder.is_dir() and not any(folder.iterdir()):
                    folder.rmdir()
            except OSError:
                pass

        return restored, errors

    def _undo_done(self, result):
        restored, errors = result
        self.last_moves = []
        self.undo_btn.state(["disabled"])
        self.clear_duplicates()
        self.set_status(f"↩ Restored {restored} files")
        if errors:
            messagebox.showwarning(
                "Undo finished with errors",
                f"{len(errors)} file(s) could not be restored:\n" + "\n".join(errors[:10])
            )

    # Find Duplicate Files

    def find_duplicates(self):
        if not self.require_folder():
            return
        self.run_task("🧩 Looking for duplicates...", self._duplicates_work,
                      self._duplicates_done)

    def _duplicates_work(self, progress):
        # Only files with identical sizes can be duplicates, so group by size first
        by_size = defaultdict(list)
        for item in iter_files(self.folder):
            try:
                size = item.stat().st_size
            except OSError:
                continue
            if size > 0:
                by_size[size].append(item)

        candidates = [
            (item, size)
            for size, items in by_size.items() if len(items) > 1
            for item in items
        ]

        by_hash = defaultdict(list)
        for index, (item, size) in enumerate(candidates, 1):
            try:
                by_hash[(size, file_hash(item))].append(item)
            except OSError:
                pass
            progress(index, len(candidates))

        results = []
        for (size, _), files in by_hash.items():
            if len(files) < 2:
                continue
            # Prefer a filename without "copy" as original
            files.sort(key=lambda p: ("copy" in p.stem.lower(), len(str(p)), str(p).lower()))
            original, *duplicates = files
            for duplicate in duplicates:
                results.append((duplicate, original, size))
        return results

    def _duplicates_done(self, results):
        self.clear_duplicates()
        for duplicate, original, size in results:
            item_id = self.tree.insert("", tk.END, values=(
                duplicate.relative_to(self.folder),
                original.relative_to(self.folder),
                human_size(size),
            ))
            self.duplicates[item_id] = (duplicate, size)

        if results:
            wasted = sum(size for _, _, size in results)
            self.set_status(
                f"🧩 {len(results)} duplicate files found ({human_size(wasted)} reclaimable)"
            )
        else:
            self.set_status("✅ No duplicate files found")
            messagebox.showinfo("Result", "No duplicate files found!")

    # Delete Selected Duplicate Files

    def select_all_duplicates(self):
        self.tree.selection_set(self.tree.get_children())

    def delete_selected_duplicates(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a duplicate file!")
            return

        total_size = sum(self.duplicates[item_id][1] for item_id in selected)
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Permanently delete {len(selected)} duplicate file(s) "
            f"({human_size(total_size)})?\nThe original copies will be kept."
        ):
            return

        deleted = 0
        errors = []
        for item_id in selected:
            path, _ = self.duplicates[item_id]
            try:
                if path.is_file():
                    path.unlink()
                    deleted += 1
                self.tree.delete(item_id)
                del self.duplicates[item_id]
            except OSError as error:
                errors.append(f"{path.name}: {error}")

        self.set_status(f"🗑 Deleted {deleted} duplicate file(s)")
        if errors:
            messagebox.showerror(
                "Delete Error",
                f"{len(errors)} file(s) could not be deleted:\n" + "\n".join(errors[:10])
            )
        else:
            messagebox.showinfo("Success", f"{deleted} duplicate file(s) deleted successfully!")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
