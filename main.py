from collections import defaultdict, Counter
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import shutil
import hashlib

selected_folder = None
duplicate_paths = []


# Choose Folder
def choose_folder():
    global selected_folder

    folder = filedialog.askdirectory(title="Select a folder")

    if folder:
        selected_folder = Path(folder)
        folder_label.config(text=str(selected_folder))
        status_label.config(text="Folder selected")

        output.delete("1.0", tk.END)
        duplicate_list.delete(0, tk.END)
        duplicate_paths.clear()


# Scan Files
def scan_files():
    if selected_folder is None:
        messagebox.showwarning("Warning", "Select a folder first!")
        return

    files = [
        f for f in selected_folder.rglob("*")
        if f.is_file()
    ]

    extensions = Counter(
        f.suffix.lower() or "No extension"
        for f in files
    )

    output.delete("1.0", tk.END)
    output.insert(tk.END, f"Total files: {len(files)}\n\n")

    for ext, count in sorted(extensions.items()):
        output.insert(tk.END, f"{ext}: {count} file(s)\n")

    status_label.config(text="Scan completed")


# Organize Files
def organize_files():
    if selected_folder is None:
        messagebox.showwarning("Warning", "Select a folder first!")
        return

    file_types = {
        "Images": [".jpg", ".jpeg", ".png", ".gif"],
        "Documents": [".txt", ".pdf", ".docx", ".doc"],
        "Videos": [".mp4", ".mkv", ".avi"],
        "Others": []
    }

    moved = 0
    category_names = set(file_types.keys())

    for item in selected_folder.rglob("*"):
        if not item.is_file():
            continue

        # Skip files already inside category folders
        if item.relative_to(selected_folder).parts[0] in category_names:
            continue

        extension = item.suffix.lower()
        category = "Others"

        for name, extensions in file_types.items():
            if extension in extensions:
                category = name
                break

        destination_folder = selected_folder / category
        destination_folder.mkdir(exist_ok=True)

        destination = destination_folder / item.name

        if destination.exists():
            continue

        try:
            shutil.move(str(item), str(destination))
            moved += 1
        except OSError as e:
            messagebox.showerror("Move Error", str(e))

    status_label.config(text=f"Organized: {moved} files")

    messagebox.showinfo(
        "Completed",
        f"{moved} files organized successfully!"
    )


# Find Duplicate Files
def find_duplicates(show_message=True):
    global duplicate_paths

    if selected_folder is None:
        messagebox.showwarning("Warning", "Select a folder first!")
        return

    file_hashes = defaultdict(list)

    for item in selected_folder.rglob("*"):
        if item.is_file():
            try:
                hasher = hashlib.sha256()

                with open(item, "rb") as f:
                    for chunk in iter(
                        lambda: f.read(1024 * 1024), b""
                    ):
                        hasher.update(chunk)

                file_hashes[hasher.hexdigest()].append(item)

            except OSError:
                continue

    duplicate_paths = []
    duplicate_list.delete(0, tk.END)

    for files in file_hashes.values():
        if len(files) > 1:

            # Prefer a filename without "copy" as original
            original = sorted(
                files,
                key=lambda p: (
                    "copy" in p.stem.lower(),
                    str(p).lower()
                )
            )[0]

            for duplicate in files:
                if duplicate != original:
                    duplicate_paths.append(duplicate)

                    duplicate_list.insert(
                        tk.END,
                        f"{duplicate.name} | Original: {original.name}"
                    )

    if duplicate_paths:
        status_label.config(
            text=f"{len(duplicate_paths)} duplicate files found"
        )
    else:
        status_label.config(text="No duplicate files found")

        if show_message:
            messagebox.showinfo(
                "Result",
                "No duplicate files found!"
            )


# Delete Selected Duplicate Files
def delete_selected_duplicates():
    selected = duplicate_list.curselection()

    if not selected:
        messagebox.showwarning(
            "Warning",
            "Please select a duplicate file!"
        )
        return

    confirm = messagebox.askyesno(
        "Confirm Delete",
        "Are you sure you want to delete selected duplicate files?"
    )

    if not confirm:
        return

    deleted_count = 0

    for index in reversed(selected):
        file_path = duplicate_paths[index]

        try:
            if file_path.exists() and file_path.is_file():
                file_path.unlink()
                deleted_count += 1

        except OSError as e:
            messagebox.showerror("Delete Error", str(e))

    # Refresh duplicate list after deletion
    find_duplicates(show_message=False)

    messagebox.showinfo(
        "Success",
        f"{deleted_count} duplicate file(s) deleted successfully!"
    )


# Main Window
root = tk.Tk()
root.title("Smart File Organizer & Duplicate Finder")

root.geometry("750x650")
root.configure(bg="#f4f6f9")

title = tk.Label(
    root,
    text="📁 Smart File Organizer & Duplicate Finder",
    font=("Segoe UI", 20, "bold"),
    bg="#f4f6f9",
    fg="#2c3e50"
)
title.pack(pady=15)
tk.Button(
    root,
    text="📂 Choose Folder",
    command=choose_folder,
    bg="#3498db",
    fg="white",
    font=("Segoe UI", 10, "bold"),
    cursor="hand2"
).pack(pady=5)

folder_label = tk.Label(
    root,
    text="No folder selected",
    wraplength=700,
    bg="#f4f6f9",
    fg="#555555",
    font=("Segoe UI", 10)
)
folder_label.pack(pady=5)

action_frame = tk.Frame(root, bg="#f4f6f9")
action_frame.pack(pady=10)

scan_btn = tk.Button(
    action_frame,
    text="🔍 Scan Files",
    command=scan_files,
    bg="#3498db",
    fg="white",
    font=("Segoe UI", 10, "bold")
)
scan_btn.pack(side="left", padx=10)

organize_btn = tk.Button(
    action_frame,
    text="📁 Organize Files",
    command=organize_files,
    bg="#2ecc71",
    fg="white",
    font=("Segoe UI", 10, "bold")
)
organize_btn.pack(side="left", padx=10)

duplicate_btn = tk.Button(
    action_frame,
    text="🧩 Find Duplicates",
    command=find_duplicates,
    bg="#9b59b6",
    fg="white",
    font=("Segoe UI", 10, "bold")
)
duplicate_btn.pack(side="left", padx=10)

list_frame = tk.Frame(root, bd=2, relief="groove", bg="white")
list_frame.pack(padx=15, pady=5)
duplicate_list = tk.Listbox(
    root,
    width=80,
    height=6,
    font=("Segoe UI", 10),
    bd=1,
    relief="solid"
)
duplicate_list.pack()
scrollbar = tk.Scrollbar(root)
scrollbar.pack(side="right", fill="y")

duplicate_list.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=duplicate_list.yview)
tk.Button(
    root,
    text="Delete Selected Duplicates",
    command=delete_selected_duplicates,
    bg="#e74c3c",
    fg="white"
).pack(pady=8)
# Results Title
result_label = tk.Label(
    root,
    text="📊 Scan Results",
    font=("Segoe UI", 12, "bold"),
    bg="#f4f6f9",
    fg="#2c3e50"
)
result_label.pack(pady=(10, 5))
output = tk.Text(
    root,
    height=8,
    width=80,
    font=("Consolas", 10),
    bd=1,
    relief="solid"
)
output.pack(padx=10, pady=5)

status_label = tk.Label(
    root,
    text="✅ Ready",
    bg="#ecf0f1",
    font=("Segoe UI", 10, "bold"),
    anchor="w"
)
status_label.pack(pady=5)

root.mainloop()
