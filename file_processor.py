import os
from pathlib import Path
from CppParser import ClangCppParser

class FileProcessor:
    def __init__(self, log_func, update_progress):
        self.log_func = log_func
        self.update_progress = update_progress

    def run_processing(self, header_file, cpp_file, output_folder_name):
        """Run the file processing"""
        try:
            self.log_func(f"Processing header file: {header_file}")
            self.log_func(f"Processing Source Cpp file: {cpp_file}")

            # Read and log initial content
            with open(cpp_file, 'r') as f:
                cpp_content = f.read()

            # Calculate initial metrics
            initial_chars = len(cpp_content)
            initial_words = len(cpp_content.split())
            initial_lines = len(cpp_content.splitlines())

            self.log_func("--- Initial Metrics ---")
            self.log_func(f"Characters: {initial_chars}")
            self.log_func(f"Words: {initial_words}")
            self.log_func(f"Lines: {initial_lines}")

            # Update progress bar
            self.update_progress(10)

            # Create parser
            parser = ClangCppParser()

            # Extract functions from header file
            self.log_func("Extracting functions from header file...")
            header_functions, function_metadata = parser.extract_header_functions(header_file)

            if not header_functions:
                self.log_func("Warning: No function declarations found in header file")
                return

            # Update progress bar
            self.update_progress(30)

            # Create an order mapping for header functions
            function_order = {sig: i for i, sig in enumerate(header_functions.keys())}

            # Extract functions from Source Cpp file
            self.log_func("Extracting functions from Source Cpp file...")
            cpp_functions = parser.extract_cpp_functions(cpp_file, header_functions, function_metadata)

            if not cpp_functions:
                self.log_func("Warning: No function Source Cpps found in source file")
                return

            # Update progress bar
            self.update_progress(50)

            # Reorder Source Cpp functions
            self.log_func("Reordering functions...")
            reordered_content = parser.reorder_cpp_content(cpp_file, function_order, cpp_functions, function_metadata, log_func=self.log_func)

            # Update progress bar
            self.update_progress(70)

            # Calculate reordered metrics
            reordered_chars = len(reordered_content)
            reordered_words = len(reordered_content.split())
            reordered_lines = len(reordered_content.splitlines())

            self.log_func("--- Reordered Metrics ---")
            self.log_func(f"Characters: {reordered_chars}")
            self.log_func(f"Words: {reordered_words}")
            self.log_func(f"Lines: {reordered_lines}")

            # Check for potential content loss
            if initial_chars != reordered_chars:
                self.log_func(f"Warning: Character count differs (Before: {initial_chars}, After: {reordered_chars})")
            if initial_words != reordered_words:
                self.log_func(f"Warning: Word count differs (Before: {initial_words}, After: {reordered_words})")

            # Update progress bar
            self.update_progress(90)

            # Create output folder if it doesn't exist
            output_folder = Path(output_folder_name)
            output_folder.mkdir(exist_ok=True)

            # Write output file
            output_file = output_folder / Path(cpp_file).name
            with open(output_file, 'w') as f:
                f.write(reordered_content)

            self.log_func(f"Successfully reordered functions in {output_file}")

            # Complete progress bar
            self.update_progress(100)

        except Exception as e:
            self.log_func(f"Error processing files: {e}")
            import traceback
            self.log_func(traceback.format_exc())
