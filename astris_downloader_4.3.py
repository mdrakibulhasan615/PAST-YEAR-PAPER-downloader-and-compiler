import os
import sys
import requests
import shutil
import threading
import warnings
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pypdf import PdfWriter, PdfReader
from PIL import Image, ImageTk
import gspread
from google.oauth2.service_account import Credentials

# --- RECURSION & WARNINGS ---
sys.setrecursionlimit(2000)
warnings.filterwarnings("ignore")

# --- CONFIG & GLOBALS ---
CONFIG_FILE = "config.txt"
BASE_URL = "https://pastpapers.papacambridge.com/download_file.php?files=https://pastpapers.papacambridge.com/directories/CAIE/CAIE-pastpapers/upload/"

SEASONS = {
    "m": ["1", "2", "3", "4", "5", "6"], 
    "s": ["1", "2", "3", "4", "5", "6"], 
    "w": ["1", "2", "3", "4", "5", "6"]
}

NOW = datetime.now()
CURRENT_YEAR = NOW.year
CURRENT_MONTH = NOW.month 

YEARS = list(range(2016, CURRENT_YEAR + 1))
PAPERS = ["1", "2", "3", "4", "5", "6"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

DEFAULT_FALLBACK = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop", "Astris Subjects")

stop_event = threading.Event()
dark_mode = True

# --- GLOBAL OPTIMIZATIONS ---
http_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=15, pool_maxsize=15)
http_session.mount('https://', adapter)
http_session.headers.update(HEADERS)

# --- ABSOLUTE PATH AUTHENTICATION FIX ---
# Locates the script's directory even when launched from CMD
script_dir = os.path.dirname(os.path.abspath(__file__))
creds_path = os.path.join(script_dir, "credentials.json")

print(f"--- PATH DEBUGGER ---")
print(f"Script Directory: {script_dir}")
print(f"Looking for Credentials at: {creds_path}")

g_sheet = None
auth_error = None 

if os.path.exists(creds_path):
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        client = gspread.authorize(creds)
        g_sheet = client.open("ASTRIS Data").sheet1
        print("Google Sheets: Connection Successful!")
    except Exception as e:
        auth_error = f"Auth failed: {str(e)}"
        print(f"Google Sheets Error: {auth_error}")
else:
    auth_error = "File credentials.json not found in script directory."
    print(f"Critical Error: {auth_error}")

# --- HELPER FUNCTIONS ---

def load_default_path():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            saved_path = f.read().strip()
            if os.path.exists(saved_path): return saved_path
    return DEFAULT_FALLBACK

def save_default_path(path):
    with open(CONFIG_FILE, "w") as f: f.write(path)

def update_status(text):
    if root: root.after(0, lambda: status_label.config(text=text))

def update_progress(value):
    if root: root.after(0, lambda: progress_var.set(value))

def add_placeholder(entry, text):
    entry.insert(0, text)
    entry.config(foreground="gray")
    def on_focus_in(event):
        if entry.get() == text:
            entry.delete(0, tk.END)
            entry.config(foreground="white" if dark_mode else "black")
    def on_focus_out(event):
        if entry.get() == "":
            entry.insert(0, text)
            entry.config(foreground="gray")
    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)

# --- CORE LOGIC ---

def create_folders(base):
    for r in ["16-25", "20-25", "ALL"]:
        os.makedirs(os.path.join(base, r), exist_ok=True)
        if r != "ALL":
            for p in range(1, 7):
                for t in ["Q", "MS"]:
                    os.makedirs(os.path.join(base, r, f"P{p}", t), exist_ok=True)

def download_and_sort(task):
    if stop_event.is_set(): return None
    year, season, paper, variant, ftype, subject_code, all_folder = task
    
    if year == CURRENT_YEAR:
        if season == "m" and CURRENT_MONTH < 5: return None
        if season == "s" and CURRENT_MONTH < 8: return None
        if season == "w" and CURRENT_MONTH < 12: return None

    year_short = str(year)[-2:]
    filename = f"{subject_code}_{season}{year_short}_{ftype}_{paper}{variant}.pdf"
    save_path = os.path.join(all_folder, filename)

    if os.path.exists(save_path): 
        return ("SUCCESS", year, season, paper, variant, filename)

    url = BASE_URL + filename
    
    # RETRY LOGIC (3 Tries) + 30s TIMEOUT
    for attempt in range(3):
        try:
            r = http_session.get(url, timeout=30) 
            if r.status_code == 200 and r.content.startswith(b"%PDF"):
                with open(save_path, "wb") as f:
                    f.write(r.content)
                return ("SUCCESS", year, season, paper, variant, filename)
            elif r.status_code == 404:
                return ("NOT_FOUND", year, season, paper, variant, filename)
        except Exception:
            if attempt == 2:
                return ("ERROR", year, season, paper, variant, f"{filename} (Timeout)")
            continue
            
    return ("NOT_FOUND", year, season, paper, variant, filename)

def run_downloader(subject_name, subject_code):
    base_path = os.path.join(selected_path.get(), subject_name)
    all_folder = os.path.join(base_path, "ALL")
    create_folders(base_path)
    tasks = []
    for year in YEARS:
        for season, variants in SEASONS.items():
            for paper in PAPERS:
                for variant in variants:
                    for ftype in ["qp", "ms"]:
                        tasks.append((year, season, paper, variant, ftype, subject_code, all_folder))

    total_tasks = len(tasks)
    completed = 0
    results = []
    update_status("Downloading...")

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(download_and_sort, t) for t in tasks]
        for future in as_completed(futures):
            if stop_event.is_set(): break
            res = future.result()
            if res: results.append(res)
            completed += 1
            if completed % 10 == 0: update_progress(int((completed / total_tasks) * 100))

    if not stop_event.is_set():
        update_status("Finalizing...")
        existing_profile = set()
        error_list = []
        for status, year, season, paper, variant, fname in results:
            if status == "SUCCESS": existing_profile.add((season, paper, variant))
            elif status == "ERROR": error_list.append(fname)

        missing_list = []
        for status, year, season, paper, variant, fname in results:
            if status == "NOT_FOUND" and (season, paper, variant) in existing_profile:
                if year < CURRENT_YEAR: missing_list.append(fname)

        update_status("Done!")
        report = f"Subject: {subject_name}\n"
        if missing_list:
            report += f"\n--- {len(missing_list)} Missing ---\n" + "\n".join(sorted(missing_list)[:10])
        if error_list:
            report += f"\n\n--- {len(error_list)} Timeouts ---\n" + "\n".join(error_list[:10])
        messagebox.showinfo("Final Report", report)

# --- COMPILER LOGIC ---

def get_sort_key(filename):
    try:
        parts = filename.split('_')
        season_order = {'m': 1, 's': 2, 'w': 3}.get(parts[1][0], 4)
        return (int(parts[1][1:]), season_order, parts[3].replace('.pdf', ''))
    except: return (999, 9, filename)

def merge_and_cleanup(folder, subject_name):
    folder = os.path.normpath(folder)
    if not os.path.exists(folder): return None
    files = [f for f in os.listdir(folder) if f.endswith(".pdf")]
    if not files: return None
    files.sort(key=get_sort_key)
    writer = PdfWriter()
    file_paths = []
    for file in files:
        path = os.path.join(folder, file)
        try:
            writer.append(path)
            file_paths.append(path)
        except: continue
    parts = folder.split(os.sep)
    year_range, paper_folder, type_folder = parts[-3], parts[-2], parts[-1]
    final_name = f"{subject_name} {paper_folder} {year_range} {type_folder}.pdf"
    master_path = os.path.join(folder, final_name)
    try:
        page_count = len(writer.pages)
        with open(master_path, "wb") as output_file: writer.write(output_file)
        writer.close()
        
        # Row format for Google Sheets
        row_data = [subject_name, paper_folder, year_range, type_folder, page_count]
        for path in file_paths:
            try: os.remove(path)
            except: pass
        return row_data
    except: return None

def run_compiler(subject_name, all_folder):
    base_path = os.path.dirname(all_folder)
    create_folders(base_path)
    files = [f for f in os.listdir(all_folder) if f.endswith(".pdf")]
    if not files:
        messagebox.showerror("Error", "No PDFs found.")
        return
    
    update_status("Sorting...")
    for i, filename in enumerate(files):
        if stop_event.is_set(): break
        try:
            parts = filename.split('_')
            year, ftype, paper = 2000 + int(parts[1][1:]) , parts[2], parts[3][0]
            type_folder = "Q" if ftype == "qp" else "MS"
            src_path = os.path.join(all_folder, filename)
            shutil.copy(src_path, os.path.join(base_path, "16-25", f"P{paper}", type_folder, filename))
            if year >= 2020:
                shutil.copy(src_path, os.path.join(base_path, "20-25", f"P{paper}", type_folder, filename))
        except: pass
        update_progress(int(((i + 1) / len(files)) * 50))

    if not stop_event.is_set():
        update_status("Merging...")
        folders_to_merge = []
        for r in ["16-25", "20-25"]:
            for p in range(1, 7):
                for t in ["Q", "MS"]:
                    folders_to_merge.append(os.path.join(base_path, r, f"P{p}", t))
        
        all_sheet_rows = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_folder = {executor.submit(merge_and_cleanup, folder, subject_name): folder for folder in folders_to_merge}
            for i, future in enumerate(as_completed(future_to_folder)):
                res = future.result()
                if res: all_sheet_rows.append(res)
                update_progress(50 + int(((i + 1) / len(folders_to_merge)) * 50))

        # Google Sheets upload with error handling
        if all_sheet_rows and not stop_event.is_set():
            if g_sheet:
                try: 
                    g_sheet.append_rows(all_sheet_rows, value_input_option="USER_ENTERED")
                except Exception as e: 
                    messagebox.showerror("Sheet Error", str(e))
            else:
                messagebox.showwarning("Auth Error", f"Sheet skipped. Reason: {auth_error}")

        update_status("Complete!")
        messagebox.showinfo("Success", "Master PDFs ready.")

# --- GUI ACTIONS ---

def start_action():
    stop_event.clear()
    name = name_entry.get().strip()
    if app_mode.get() == "Download":
        code = code_entry.get().strip()
        if name and code and name != "Subject Name":
            threading.Thread(target=run_downloader, args=(name, code), daemon=True).start()
    else:
        if name and name != "Subject Name":
            all_folder = filedialog.askdirectory(title="Select 'ALL' Folder")
            if all_folder: threading.Thread(target=run_compiler, args=(name, all_folder), daemon=True).start()

def apply_theme():
    bg, fg = ("#0f1117", "#ffffff") if dark_mode else ("#f0f2f5", "#1c1e21")
    root.configure(bg=bg)
    main_frame.configure(bg=bg)
    status_label.configure(bg=bg, fg=fg)
    path_label.configure(bg=bg, fg=fg)
    name_entry.config(bg="#1c1e21" if dark_mode else "#ffffff", insertbackground=fg)
    code_entry.config(bg="#1c1e21" if dark_mode else "#ffffff", insertbackground=fg)
    mode_frame.configure(bg=bg)
    rb_download.configure(bg=bg, fg=fg, selectcolor="#2c313c" if dark_mode else "#e4e6eb")
    rb_compile.configure(bg=bg, fg=fg, selectcolor="#2c313c" if dark_mode else "#e4e6eb")
    if logo_label:
        img = logo_dark if dark_mode else logo_light
        if img: logo_label.config(image=img, bg=bg)

root = tk.Tk()
root.title("ASTRIS - CAIE Master")
root.geometry("450x550")
root.resizable(False, False)

selected_path = tk.StringVar(value=load_default_path())
app_mode = tk.StringVar(value="Download")

menu_bar = tk.Menu(root)
root.config(menu=menu_bar)
settings_menu = tk.Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="Menu", menu=settings_menu)
settings_menu.add_command(label="Change Folder", command=lambda: selected_path.set(filedialog.askdirectory() or selected_path.get()))
settings_menu.add_command(label="Set Default", command=lambda: save_default_path(selected_path.get()))
settings_menu.add_command(label="Toggle Theme", command=lambda: [globals().update(dark_mode=not dark_mode), apply_theme()])

logo_dark = logo_light = None
try:
    logo_dark = ImageTk.PhotoImage(Image.open(os.path.join(script_dir, "logo_dark.png")).resize((260, 100)))
    logo_light = ImageTk.PhotoImage(Image.open(os.path.join(script_dir, "logo_light.png")).resize((260, 100)))
except: pass

main_frame = tk.Frame(root)
main_frame.pack(fill="both", expand=True, padx=40, pady=20)
logo_label = tk.Label(main_frame, bd=0)
logo_label.pack(pady=(0, 10))

name_entry = tk.Entry(main_frame, justify="center", relief="solid", bd=1)
name_entry.pack(fill="x", pady=5, ipady=3)
add_placeholder(name_entry, "Subject Name")

code_entry = tk.Entry(main_frame, justify="center", relief="solid", bd=1)
code_entry.pack(fill="x", pady=5, ipady=3)
add_placeholder(code_entry, "Subject Code")

path_label = tk.Label(main_frame, textvariable=selected_path, wraplength=350, font=("Arial", 8))
path_label.pack(pady=10)

mode_frame = tk.Frame(main_frame)
mode_frame.pack(pady=5)
rb_download = tk.Radiobutton(mode_frame, text="Download", variable=app_mode, value="Download")
rb_download.pack(side="left", padx=10)
rb_compile = tk.Radiobutton(mode_frame, text="Compile", variable=app_mode, value="Compile")
rb_compile.pack(side="left", padx=10)

ttk.Button(main_frame, text="START ACTION", command=start_action).pack(fill="x", pady=5)
ttk.Button(main_frame, text="STOP", command=lambda: stop_event.set()).pack(fill="x", pady=5)
progress_var = tk.IntVar()
ttk.Progressbar(main_frame, maximum=100, variable=progress_var).pack(fill="x", pady=15)
status_label = tk.Label(main_frame, text="Ready", font=("Arial", 10, "bold"))
status_label.pack()

apply_theme()
root.mainloop()