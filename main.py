import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import threading
from pathlib import Path
from CppParser import CppParser  # Import the CppParser from the main file

class CppReorderGUI:
    """GUI Tool for the C++ Function Reordering Tool"""

    def __init__(self, root):
        self.root = root
        self.root.title("C++ Function Reorderer")
        self.root.geometry("800x600")
        self.root.minsize(700, 500)

        self.header_path = tk.StringVar()
        self.cpp_path = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.status = tk.StringVar()
        self.status.set("Ready")

        self.setup_ui()

    def setup_ui(self):
        """Set up the GUI components"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # File selection area
        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding="10")
        file_frame.pack(fill=tk.X, padx=5, pady=5)

        # Header file
        ttk.Label(file_frame, text="Header File (.h):").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(file_frame, textvariable=self.header_path, width=50).grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(file_frame, text="Browse...", command=self.browse_header).grid(row=0, column=2, padx=5, pady=5)

        # CPP file
        ttk.Label(file_frame, text="Implementation File (.cpp):").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(file_frame, textvariable=self.cpp_path, width=50).grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(file_frame, text="Browse...", command=self.browse_cpp, state=tk.DISABLED).grid(row=1, column=2, padx=5, pady=5)

        # Output options
        options_frame = ttk.LabelFrame(main_frame, text="Output Options", padding="10")
        options_frame.pack(fill=tk.X, padx=5, pady=10)

        # Output folder name
        ttk.Label(options_frame, text="Output Folder Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(options_frame, textvariable=self.output_folder, width=50, state='readonly').grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)

        options_frame.columnconfigure(1, weight=1)

        # Status area
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.log_text = tk.Text(status_frame, height=20, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_text.config(state=tk.DISABLED)

        scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

        # Bottom status bar
        status_bar = ttk.Label(main_frame, textvariable=self.status, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Process Files", command=self.process_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Exit", command=self.root.destroy).pack(side=tk.LEFT, padx=5)

        # Configure row and column weights for resizing
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        status_frame.columnconfigure(0, weight=1)
        status_frame.rowconfigure(0, weight=1)

    def browse_header(self):
        """Browse for header file and set CPP file automatically"""
        filename = filedialog.askopenfilename(
            title="Select Header File",
            filetypes=(("Header files", "*.h *.hpp"), ("All files", "*.*"))
        )
        if filename:
            self.header_path.set(filename)
            # Automatically set the CPP path
            cpp_filename = Path(filename).with_suffix('.cpp')
            if cpp_filename.exists():
                self.cpp_path.set(str(cpp_filename))
            else:
                messagebox.showwarning("Warning", f"No corresponding .cpp file found for {filename}")

            # Set the output folder path
            output_folder_path = Path(filename).parent / "reordered_output"
            self.output_folder.set(str(output_folder_path))

    def browse_cpp(self):
        """Browse for implementation file"""
        filename = filedialog.askopenfilename(
            title="Select Implementation File",
            filetypes=(("C++ files", "*.cpp *.cc"), ("All files", "*.*"))
        )
        if filename:
            self.cpp_path.set(filename)

    def log(self, message):
        """Add message to log area"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def log_functions_to_file(self, message):
        """Log function list to log file"""
        with open("log.txt", "a") as log_file:
            log_file.write(message + "\n")

    def process_files(self):
        """Process the selected files"""
        header_file = self.header_path.get()
        cpp_file = self.cpp_path.get()
        output_folder_name = self.output_folder.get()

        # Validate inputs
        if not header_file:
            messagebox.showerror("Error", "Please select a header file.")
            return
        if not cpp_file:
            messagebox.showerror("Error", "Please select an implementation file.")
            return

        # Clear previous log
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

        # Clear log file
        with open("log.txt", "w") as log_file:
            log_file.write("")

        # Update status
        self.status.set("Processing...")
        self.root.update_idletasks()

        # Run the processing in a separate thread to keep the GUI responsive
        threading.Thread(target=self.run_processing, args=(header_file, cpp_file, output_folder_name)).start()

    def run_processing(self, header_file, cpp_file, output_folder_name):
        """Run the file processing in a separate thread"""
        try:
            # Read input files
            with open(header_file, 'r') as f:
                header_content = f.read()

            with open(cpp_file, 'r') as f:
                cpp_content = f.read()

            # Parse files
            parser = CppParser()
            header_functions = parser.extract_header_functions(header_content)
            function_order = {sig: i for i, sig in enumerate(header_functions.keys())}
            cpp_functions = parser.extract_cpp_functions(cpp_content, header_functions)

            if not cpp_functions:
                self.log("Warning: No function implementations found in source file")
                self.status.set("Ready")
                return

            # Log initial function list
            self.log_functions_to_file("--- Functions in CPP Before Sorting ---")
            for func in cpp_functions:
                self.log_functions_to_file(f"{func.signature} (Line: {func.index})")

            # Reorder implementation functions
            reordered_content = parser.reorder_cpp_content(cpp_content, function_order, cpp_functions, log_func=self.log)

            # Create output folder if it doesn't exist
            output_folder = Path(output_folder_name)
            output_folder.mkdir(exist_ok=True)

            # Write output file
            output_file = output_folder / Path(cpp_file).name
            with open(output_file, 'w') as f:
                f.write(reordered_content)

            # Log final function list
            self.log_functions_to_file("--- Functions in CPP After Sorting ---")
            sorted_functions = parser.extract_cpp_functions(reordered_content, header_functions)
            for func in sorted_functions:
                self.log_functions_to_file(f"{func.signature} (Line: {func.index})")

            self.log(f"Successfully reordered functions in {output_file}")
            self.status.set("Ready")

        except Exception as e:
            self.log(f"Error processing files: {e}")
            self.status.set("Ready")
            import traceback
            traceback.print_exc()

def run_gui():
    """Run the GUI application"""
    root = tk.Tk()
    app = CppReorderGUI(root)
    root.mainloop()

if __name__ == "__main__":
    run_gui()
