import argparse
import os
from pathlib import Path
from CppParser import ClangCppParser  # Assuming this is where ClangCppParser is defined

class FileProcessor:
    def __init__(self, log_func, update_progress):
        self.log_func = log_func
        self.update_progress = update_progress

    def run_processing(self, header_file, cpp_file, output_folder_name, config=None, dry_run=False):
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

            # Create parser with layout config if provided
            parser = ClangCppParser(config)

            # Extract functions from header file
            self.log_func("Extracting functions from header file...")
            header_functions, function_order = parser.parse_header_file(header_file)

            if not header_functions:
                self.log_func("Warning: No function declarations found in header file")
                return

            # Update progress bar
            self.update_progress(30)

            # Extract functions from Source Cpp file
            self.log_func("Extracting functions from Source Cpp file...")
            cpp_functions = parser.parse_source_file(cpp_file, header_functions)

            if not cpp_functions:
                self.log_func("Warning: No function implementations found in source file")
                return

            # Update progress bar
            self.update_progress(50)

            # Reorder Source Cpp functions
            self.log_func("Reordering functions...")
            reordered_content = parser.reorder_functions(cpp_file, cpp_functions, function_order)

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

            if dry_run:
                self.log_func("Dry run completed. No files were modified.")
                self.log_func(reordered_content)
            else:
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

def main():
    """Main entry point for the command-line interface"""
    parser = argparse.ArgumentParser(
        description='Reorder C++ functions in header and source files according to layout rules'
    )
    parser.add_argument('header', help='Path to the header file (.h/.hpp)')
    parser.add_argument('source', help='Path to the source file (.cpp/.cc)')
    parser.add_argument('-o', '--output', help='Output folder (defaults to current directory)')
    parser.add_argument('-c', '--config', help='Path to layout rules configuration file (JSON)')
    parser.add_argument('--dry-run', action='store_true', help='Print result without writing to file')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')

    args = parser.parse_args()

    # Validate file extensions
    if not args.header.endswith(('.h', '.hpp')):
        print(f"Error: Header file should have .h or .hpp extension: {args.header}")
        return 1

    if not args.source.endswith(('.cpp', '.cc')):
        print(f"Error: Source file should have .cpp or .cc extension: {args.source}")
        return 1

    # Check if files exist
    if not os.path.isfile(args.header):
        print(f"Error: Header file not found: {args.header}")
        return 1

    if not os.path.isfile(args.source):
        print(f"Error: Source file not found: {args.source}")
        return 1

    # Define log and progress update functions
    def log_func(message):
        if args.verbose:
            print(message)

    def update_progress(percentage):
        if args.verbose:
            print(f"Progress: {percentage}%")

    # Create FileProcessor instance and run processing
    processor = FileProcessor(log_func, update_progress)
    processor.run_processing(args.header, args.source, args.output or ".", args.config, args.dry_run)

    return 0

if __name__ == "__main__":
    main()