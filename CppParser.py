#!/usr/bin/env python3
"""
C++ Function Reordering Tool

This script rearranges function implementations in a C++ source file (.cpp)
to match the order of function declarations in the corresponding header file (.h).
Features both command line and GUI interfaces.
"""

import re
import os
import sys
import argparse
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

class FunctionInfo:
    """Class to store information about a function"""
    def __init__(self, name, signature, full_text, index):
        self.name = name
        self.signature = signature
        self.full_text = full_text
        self.index = index  # Original position in the file

    def __repr__(self):
        return f"FunctionInfo(name={self.name}, index={self.index})"

class CppParser:
    """Parser for C++ header and source files"""

    def __init__(self):
        # Regex patterns for C++ parsing
        self.class_pattern = re.compile(r'class\s+(\w+)\s*(?::\s*(?:public|protected|private)\s+\w+\s*)?{')
        self.namespace_pattern = re.compile(r'namespace\s+(\w+)\s*{')
        self.header_func_pattern = re.compile(
            r'(?:virtual\s+)?(?:static\s+)?(?:const\s+)?(?:inline\s+)?'
            r'(?:explicit\s+)?(?:[a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)?\s+)?'  # return type
            r'([a-zA-Z_]\w*)\s*'  # function name
            r'\(([^)]*)\)\s*'  # parameters
            r'(?:const\s*)?(?:noexcept\s*)?(?:override\s*)?(?:final\s*)?'
            r'(?:=\s*0\s*)?(?:=\s*default\s*)?(?:=\s*delete\s*)?'
            r';'  # semicolon
        )
        self.cpp_func_pattern = re.compile(
            r'(?:static\s+)?(?:inline\s+)?'
            r'(?:[a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)?\s+)?'  # return type
            r'([a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)?)\s*::\s*([a-zA-Z_]\w*)\s*'  # class::function
            r'\(([^)]*)\)\s*'  # parameters
            r'(?:const\s*)?(?:noexcept\s*)?(?:override\s*)?(?:final\s*)?'
            r'(?:try\s*)?'
            r'{'  # opening brace
        )
        # Pattern for standalone (non-member) functions
        self.standalone_func_pattern = re.compile(
            r'(?:static\s+)?(?:inline\s+)?'
            r'(?:[a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)?\s+)'  # return type
            r'([a-zA-Z_]\w*)\s*'  # function name
            r'\(([^)]*)\)\s*'  # parameters
            r'(?:const\s*)?(?:noexcept\s*)?'
            r'(?:try\s*)?'
            r'{'  # opening brace
        )

    def normalize_params(self, params_str):
        """Normalize parameter string to help with matching"""
        # Remove parameter names, default values, and whitespace
        normalized = re.sub(r'\s*=\s*[^,)]+', '', params_str)  # Remove default values
        normalized = re.sub(r'(\w+)\s+(\w+)(?=[,)])', r'\1', normalized)  # Remove parameter names
        normalized = re.sub(r'\s+', '', normalized)  # Remove whitespace
        return normalized

    def compare_params(self, params1, params2):
        """Compare parameter lists to determine if they match"""
        return self.normalize_params(params1) == self.normalize_params(params2)

    def get_function_signature(self, name, params):
        """Create a unique signature for a function"""
        return f"{name}({self.normalize_params(params)})"

    def extract_header_functions(self, header_content):
        """Extract function declarations from header file"""
        current_class = None
        current_namespace = None
        namespaces = []
        functions = {}

        # Split by lines to track classes and namespaces
        lines = header_content.split('\n')

        for i, line in enumerate(lines):
            # Track namespaces
            namespace_match = self.namespace_pattern.search(line)
            if namespace_match:
                current_namespace = namespace_match.group(1)
                namespaces.append(current_namespace)

            # Check for namespace end
            if line.strip() == '}' and namespaces:
                namespaces.pop()
                current_namespace = namespaces[-1] if namespaces else None

            # Track classes
            class_match = self.class_pattern.search(line)
            if class_match:
                current_class = class_match.group(1)

            # Check for class end
            if line.strip() == '};':
                current_class = None

            # Extract function declarations
            func_match = self.header_func_pattern.search(line)
            if func_match:
                func_name = func_match.group(1)
                params = func_match.group(2)

                # Create fully qualified name with namespace and class if available
                qualified_name = func_name
                if current_class:
                    qualified_name = f"{current_class}::{func_name}"
                if current_namespace:
                    qualified_name = f"{current_namespace}::{qualified_name}"

                signature = self.get_function_signature(qualified_name, params)
                functions[signature] = qualified_name

        return functions

    def find_matching_function(self, cpp_name, cpp_params, header_functions):
        """Find matching header function for cpp implementation"""
        # Try direct match first
        signature = self.get_function_signature(cpp_name, cpp_params)
        if signature in header_functions:
            return signature

        # Try matching just by name and parameters
        for header_sig, header_name in header_functions.items():
            # Extract name from fully qualified header name
            parts = header_name.split('::')
            simple_name = parts[-1]

            if simple_name == cpp_name and self.compare_params(header_sig.split('(')[1], cpp_params):
                return header_sig

        return None

    def extract_cpp_functions(self, cpp_content, header_functions):
        """Extract function implementations from cpp file"""
        functions = []
        function_blocks = []
        current_block = []
        brace_count = 0
        in_function = False

        # Split content by lines for initial processing
        lines = cpp_content.split('\n')

        # First pass: identify function boundaries
        i = 0
        while i < len(lines):
            line = lines[i]

            if not in_function:
                # Check for member function implementation
                member_match = self.cpp_func_pattern.search(line)
                standalone_match = self.standalone_func_pattern.search(line)

                if member_match:
                    class_name = member_match.group(1)
                    func_name = member_match.group(2)
                    params = member_match.group(3)

                    qualified_name = f"{class_name}::{func_name}"
                    in_function = True
                    brace_count = 1
                    current_block = [i]  # Start index

                elif standalone_match:
                    func_name = standalone_match.group(1)
                    params = standalone_match.group(2)

                    qualified_name = func_name
                    in_function = True
                    brace_count = 1
                    current_block = [i]  # Start index
            else:
                # Count braces to find function end
                brace_count += line.count('{')
                brace_count -= line.count('}')

                if brace_count == 0:
                    # Function ended
                    current_block.append(i)  # End index
                    function_blocks.append(current_block)
                    current_block = []
                    in_function = False

            i += 1

        # Second pass: extract actual function text and match with header
        for start_idx, end_idx in function_blocks:
            func_text = '\n'.join(lines[start_idx:end_idx+1])

            # Extract function details
            member_match = self.cpp_func_pattern.search(lines[start_idx])
            standalone_match = self.standalone_func_pattern.search(lines[start_idx])

            if member_match:
                class_name = member_match.group(1)
                func_name = member_match.group(2)
                params = member_match.group(3)
                qualified_name = f"{class_name}::{func_name}"
            elif standalone_match:
                func_name = standalone_match.group(1)
                params = standalone_match.group(2)
                qualified_name = func_name
            else:
                continue  # Skip if not a recognized function

            # Find matching header function
            header_sig = self.find_matching_function(qualified_name, params, header_functions)

            if header_sig:
                func_info = FunctionInfo(
                    name=qualified_name,
                    signature=header_sig,
                    full_text=func_text,
                    index=start_idx
                )
                functions.append(func_info)

        return functions

    def reorder_cpp_content(self, cpp_content: str, function_order: Dict[str, int], functions: List[FunctionInfo], log_func=None) -> str:
        """Reorder functions in the cpp content based on header order"""
        if log_func:
          log_func("\n--- Function Reordering Analysis ---")
          log_func("Original function order in the .cpp file:")
          for func in functions:
              log_func(f"  - {func.signature} (Line: {func.index})")

        # Sort functions according to their order in the header file
        sorted_functions = sorted(functions, key=lambda f: function_order.get(f.signature, float('inf')))

        if log_func:
          log_func("\nFunction order in the .h file (desired order):")
          for sig, order in sorted(function_order.items(), key=lambda item: item[1]):
              log_func(f"  - {sig} (Order: {order})")

          log_func("\nReordered function order in the .cpp file:")
          for func in sorted_functions:
              log_func(f"  - {func.signature}")
          log_func("--- End of Function Reordering Analysis ---\n")

        # Split content into lines
        lines = cpp_content.split('\n')

        # Find blocks of code for each function
        blocks = []
        marked_lines = set()

        for func in functions:
            # Find the start and end lines of this function
            match_line = -1
            for i, line in enumerate(lines):
                if i in marked_lines:
                    continue

                # Check if this line contains the function signature
                if (self.cpp_func_pattern.search(line) or
                    self.standalone_func_pattern.search(line)) and func.full_text.startswith(line):
                    match_line = i
                    break

            if match_line < 0:
                continue

            # Find the end of the function
            brace_count = 0
            start_line = match_line
            end_line = match_line

            for i in range(match_line, len(lines)):
                line = lines[i]
                brace_count += line.count('{')
                brace_count -= line.count('}')
                end_line = i

                if brace_count == 0:
                    break

            # Mark these lines as part of a function
            for i in range(start_line, end_line + 1):
                marked_lines.add(i)

            blocks.append((start_line, end_line, func))

        # Separate functions from the rest of the content
        content_blocks = []
        current_pos = 0

        # Sort blocks by start position
        blocks.sort(key=lambda x: x[0])

        for start, end, func in blocks:
            # Add any content before the function
            if start > current_pos:
                content_blocks.append(('\n'.join(lines[current_pos:start]), None))
            current_pos = end + 1

        # Add any remaining content
        if current_pos < len(lines):
            content_blocks.append(('\n'.join(lines[current_pos:]), None))

        # Create new content with functions in the desired order
        new_content = []

        # Add first non-function block if it exists
        if content_blocks and content_blocks[0][1] is None:
            new_content.append(content_blocks[0][0])
            content_blocks.pop(0)

        # Add functions in the sorted order
        for func in sorted_functions:
            new_content.append(func.full_text)

        # Add any remaining non-function blocks
        for block, _ in content_blocks:
            if block.strip():
                new_content.append(block)

        return '\n\n'.join(new_content)

def main():
    parser = argparse.ArgumentParser(description='Reorder C++ functions in implementation file to match header file order')
    parser.add_argument('header', help='Path to the header file (.h)')
    parser.add_argument('implementation', help='Path to the implementation file (.cpp)')
    parser.add_argument('-o', '--output', help='Output file (defaults to overwriting implementation file)')
    parser.add_argument('--dry-run', action='store_true', help='Print result without writing to file')

    args = parser.parse_args()

    # Validate file extensions
    if not args.header.endswith(('.h', '.hpp')):
        print(f"Error: Header file should have .h or .hpp extension: {args.header}")
        return 1

    if not args.implementation.endswith(('.cpp', '.cc')):
        print(f"Error: Implementation file should have .cpp or .cc extension: {args.implementation}")
        return 1

    # Check if files exist
    if not os.path.isfile(args.header):
        print(f"Error: Header file not found: {args.header}")
        return 1

    if not os.path.isfile(args.implementation):
        print(f"Error: Implementation file not found: {args.implementation}")
        return 1

    # Read input files
    try:
        with open(args.header, 'r') as f:
            header_content = f.read()

        with open(args.implementation, 'r') as f:
            cpp_content = f.read()
    except Exception as e:
        print(f"Error reading files: {e}")
        return 1

    # Parse files
    parser = CppParser()

    try:
        # Extract functions from header file
        header_functions = parser.extract_header_functions(header_content)

        if not header_functions:
            print("Warning: No function declarations found in header file")

        # Create an order mapping for header functions
        function_order = {sig: i for i, sig in enumerate(header_functions.keys())}

        # Extract functions from implementation file
        cpp_functions = parser.extract_cpp_functions(cpp_content, header_functions)

        if not cpp_functions:
            print("Warning: No function implementations found in source file")
            return 0

        # Reorder implementation functions
        reordered_content = parser.reorder_cpp_content(cpp_content, function_order, cpp_functions)

        if args.dry_run:
            print(reordered_content)
        else:
            output_file = args.output or args.implementation
            with open(output_file, 'w') as f:
                f.write(reordered_content)
            print(f"Successfully reordered functions in {output_file}")

        return 0
    except Exception as e:
        print(f"Error processing files: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    # Check if running in GUI or CLI mode
    if len(sys.argv) > 1:
        sys.exit(main())
    else:
        from ui import run_gui
        run_gui()
