import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from pathlib import Path
from datetime import datetime
import json
from file_processor import FileProcessor

# Import the ClangCppParser class
from CppParser import ClangCppParser

CONFIG_FILE = Path.home() / "cpp_reorder_config.json"

class CppReorderGUI:
    """GUI for the C++ function reordering tool"""

    def __init__(self, root):
        self.root = root
        self.root.title("C++ Function Reordering Tool")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)

        # Set up variables
        self.header_file = tk.StringVar()
        self.cpp_file = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.status = tk.StringVar(value="Ready")

        # Set default output folder
        self.output_folder.set(os.path.join(os.path.expanduser("~"), "cpp_reordered"))

        # Load last used files
        self.load_config()

        # Create the UI
        self.create_ui()

    def create_ui(self):
        """Create the user interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Input frame
        input_frame = ttk.LabelFrame(main_frame, text="Input Files", padding="10")
        input_frame.pack(fill=tk.X, pady=5)

        # Header file selection
        ttk.Label(input_frame, text="Header File (.h):").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(input_frame, textvariable=self.header_file, width=50).grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(input_frame, text="Browse...", command=self.browse_header).grid(row=0, column=2, padx=5, pady=5)

        # CPP file selection
        ttk.Label(input_frame, text="Source Cpp File (.cpp):").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(input_frame, textvariable=self.cpp_file, width=50).grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(input_frame, text="Browse...", command=self.browse_cpp).grid(row=1, column=2, padx=5, pady=5)

        # Output folder selection
        ttk.Label(input_frame, text="Output Folder:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(input_frame, textvariable=self.output_folder, width=50).grid(row=2, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(input_frame, text="Browse...", command=self.browse_output).grid(row=2, column=2, padx=5, pady=5)

        # Configure grid
        input_frame.columnconfigure(1, weight=1)

        # Progress bar
        self.progress = ttk.Progressbar(main_frame, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(fill=tk.X, pady=10)

        # Action buttons
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=10)

        ttk.Button(action_frame, text="Process Files", command=self.process_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Clear Log", command=self.clear_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Exit", command=self.root.quit).pack(side=tk.RIGHT, padx=5)

        # Status bar
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=5)

        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        ttk.Label(status_frame, textvariable=self.status).pack(side=tk.LEFT, padx=5)

        # Log area
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=80, height=20)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Initial log message
        self.log(f"C++ Function Reordering Tool - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log("Ready to process files.")
        self.log("Please select a header file (.h) and an Source Cpp file (.cpp).")

    def browse_header(self):
        """Browse for header file"""
        filename = filedialog.askopenfilename(
            title="Select Header File",
            filetypes=[("Header Files", "*.h;*.hpp"), ("All Files", "*.*")]
        )
        if filename:
            self.header_file.set(filename)
            self.log(f"Selected header file: {filename}")
            self.save_config()

            # Set output folder to the same directory as the script with "Refactored" subfolder
            source_dir = os.path.dirname(os.path.abspath(filename))
            self.output_folder.set(os.path.join(source_dir, "Refactored"))
            self.log(f"Set output folder to Refactored: {os.path.join(source_dir, 'Refactored')}")
            
            # Try to automatically find the corresponding cpp file
            cpp_path = self._find_corresponding_cpp(filename)
            if cpp_path and os.path.isfile(cpp_path):
                self.cpp_file.set(cpp_path)
                self.log(f"Auto-detected Source Cpp file: {cpp_path}")
                self.save_config()

    def browse_cpp(self):
        """Browse for cpp file"""
        filename = filedialog.askopenfilename(
            title="Select Source Cpp File",
            filetypes=[("C++ Files", "*.cpp;*.cc"), ("All Files", "*.*")]
        )
        if filename:
            self.cpp_file.set(filename)
            self.log(f"Selected Source Cpp file: {filename}")
            self.save_config()

            # Try to automatically find the corresponding header file
            header_path = self._find_corresponding_header(filename)
            if header_path and os.path.isfile(header_path):
                self.header_file.set(header_path)
                self.log(f"Auto-detected header file: {header_path}")
                self.save_config()

    def browse_output(self):
        """Browse for output folder"""
        folder = filedialog.askdirectory(
            title="Select Output Folder"
        )
        if folder:
            self.output_folder.set(folder)
            self.log(f"Selected output folder: {folder}")
            self.save_config()

    def _find_corresponding_cpp(self, header_path):
        """Try to find the corresponding cpp file for a header file"""
        base_path = os.path.splitext(header_path)[0]
        cpp_path = base_path + ".cpp"
        cc_path = base_path + ".cc"

        if os.path.isfile(cpp_path):
            return cpp_path
        elif os.path.isfile(cc_path):
            return cc_path
        return None

    def _find_corresponding_header(self, cpp_path):
        """Try to find the corresponding header file for a cpp file"""
        base_path = os.path.splitext(cpp_path)[0]
        h_path = base_path + ".h"
        hpp_path = base_path + ".hpp"

        if os.path.isfile(h_path):
            return h_path
        elif os.path.isfile(hpp_path):
            return hpp_path
        return None

    def process_files(self):
        """Process the selected files"""
        # Validate inputs
        header_file = self.header_file.get()
        cpp_file = self.cpp_file.get()
        output_folder = self.output_folder.get()

        if not header_file:
            self.log("Error: No header file selected")
            return

        if not cpp_file:
            self.log("Error: No Source Cpp file selected")
            return

        if not output_folder:
            self.log("Error: No output folder specified")
            return

        # Validate file extensions
        if not header_file.endswith(('.h', '.hpp')):
            self.log(f"Error: Header file should have .h or .hpp extension: {header_file}")
            return

        if not cpp_file.endswith(('.cpp', '.cc')):
            self.log(f"Error: Source Cpp file should have .cpp or .cc extension: {cpp_file}")
            return

        # Check if files exist
        if not os.path.isfile(header_file):
            self.log(f"Error: Header file not found: {header_file}")
            return

        if not os.path.isfile(cpp_file):
            self.log(f"Error: Source Cpp file not found: {cpp_file}")
            return

        # Update status
        self.status.set("Processing...")
        self.log(f"Processing files: {header_file} and {cpp_file}")

        # Reset progress bar
        self.progress["value"] = 0

        # Initialize the file processor
        processor = FileProcessor(log_func=self.log, update_progress=self.update_progress)

        # Run processing in a separate thread to avoid freezing the UI
        threading.Thread(target=processor.run_processing, args=(header_file, cpp_file, output_folder), daemon=True).start()

    def update_progress(self, value):
        """Update the progress bar value"""
        self.progress["value"] = value
        self.root.update_idletasks()

    def log(self, message):
        """Add a message to the log"""
        self.log_text.insert(tk.END, str(message) + "\n")
        self.log_text.see(tk.END)  # Scroll to the end

    def clear_log(self):
        """Clear the log area"""
        self.log_text.delete(1.0, tk.END)
        self.log(f"Log cleared - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def save_config(self):
        """Save the current configuration to a file"""
        config = {
            "header_file": self.header_file.get(),
            "cpp_file": self.cpp_file.get(),
            "output_folder": self.output_folder.get()
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)

    def load_config(self):
        """Load the configuration from a file"""
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                self.header_file.set(config.get("header_file", ""))
                self.cpp_file.set(config.get("cpp_file", ""))
                self.output_folder.set(config.get("output_folder", ""))
                # Schedule the log call in the main thread
                self.root.after(0, lambda: self.log("Loaded previous configuration."))

def run_gui():
    """Run the GUI application"""
    root = tk.Tk()
    app = CppReorderGUI(root)
    root.mainloop()

if __name__ == "__main__":
    run_gui()
