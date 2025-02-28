#!/usr/bin/env python3
"""
C++ Function Reordering Tool

This script rearranges function implementations in a C++ source file (.cpp)
to match the order of function declarations in the corresponding header file (.h).
Features both command line and GUI interfaces.
"""

import os
import sys
import argparse
import json
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

# Import libclang
import clang.cindex
from clang.cindex import Index, CursorKind, TokenKind

class FunctionInfo:
    """Class to store information about a C++ function"""
    def __init__(self, name, signature, full_text, index, access_modifier=None):
        self.name = name
        self.signature = signature
        self.full_text = full_text
        self.index = index
        self.access_modifier = access_modifier

    def __str__(self):
        return f"FunctionInfo({self.name}, {self.signature}, index={self.index}, access={self.access_modifier})"

class ClangCppParser:
    """Class to store information about a function"""
    def __init__(self):
        from clang.cindex import Config, Index
        
        # List of possible libclang paths
        possible_paths = [
            "C:/Program Files/LLVM/bin/libclang.dll",
            os.path.expanduser("~/LLVM/bin/libclang.dll"),
            # Add more paths as needed (e.g., from environment variables)
            os.environ.get("LIBCLANG_PATH", "")
        ]
        
        # Try to set the library file
        for path in possible_paths:
            if path and os.path.exists(path):
                try:
                    Config.set_library_file(path)
                    print(f"Using libclang at: {path}")
                    break
                except Exception as e:
                    print(f"Failed to set libclang path {path}: {e}")
        else:
            raise RuntimeError(
                "Could not find libclang.dll. Please install LLVM and ensure "
                "libclang.dll is in one of these paths: " + ", ".join(possible_paths)
            )
        
        self.index = Index.create()
        self.compilation_flags = [
            '-x', 'c++',
            '-std=c++17',
            '-fparse-all-comments'
        ]

    def get_function_signature(self, cursor):
        """Create a unique signature for a function"""
        # Get function name
        name = cursor.spelling
        
        # Get fully qualified name
        qualified_name = self._get_fully_qualified_name(cursor)
        
        # Get parameter types
        param_types = []
        for param in cursor.get_arguments():
            param_types.append(param.type.spelling)
        
        # Create signature
        return f"{qualified_name}({','.join(param_types)})"

    def _get_fully_qualified_name(self, cursor):
        """Get fully qualified name of a cursor (including namespaces and classes)"""
        if cursor is None:
            return ""
            
        # Skip translation unit
        if cursor.kind == CursorKind.TRANSLATION_UNIT:
            return ""
            
        # Get parent's qualified name
        parent = self._get_fully_qualified_name(cursor.semantic_parent)
        
        # Add current name
        if parent:
            return f"{parent}::{cursor.spelling}"
        else:
            return cursor.spelling

    def _get_access_specifier(self, cursor):
        """Get access specifier (public, private, protected) for a cursor"""
        if cursor.access_specifier == clang.cindex.AccessSpecifier.PUBLIC:
            return "public"
        elif cursor.access_specifier == clang.cindex.AccessSpecifier.PROTECTED:
            return "protected"
        elif cursor.access_specifier == clang.cindex.AccessSpecifier.PRIVATE:
            return "private"
        else:
            return None

    def _get_comment(self, cursor):
        """Get comment associated with a cursor"""
        comment = cursor.brief_comment
        if comment:
            # Format comment with // prefix
            return "\n".join([f"// {line}" for line in comment.split('\n')])
        return ""

    def extract_header_functions(self, header_file):
        """Extract function declarations from header file"""
        tu = self.index.parse(header_file, args=self.compilation_flags)
        
        functions = {}
        function_metadata = {}
        
        # Visit all function declarations in the header
        for cursor in tu.cursor.walk_preorder():
            try:
                # Safely check cursor kind
                if cursor.kind not in [CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD, 
                                    CursorKind.CONSTRUCTOR, CursorKind.DESTRUCTOR]:
                    continue  # Skip unknown or irrelevant kinds
                    
                # Skip if this is a definition, not just a declaration
                if cursor.is_definition():
                    continue
                
                # Get function signature
                signature = self.get_function_signature(cursor)
                
                # Get fully qualified name
                qualified_name = self._get_fully_qualified_name(cursor)
                
                # Store function
                functions[signature] = qualified_name
                
                # Store metadata
                function_metadata[signature] = {
                    "access": self._get_access_specifier(cursor),
                    "class": self._get_class_name(cursor),
                    "namespace": self._get_namespace(cursor),
                    "comment": self._get_comment(cursor)
                }
            except ValueError as e:
                print(f"Warning: Skipping cursor due to unknown kind: {e}")
                continue
        
        return functions, function_metadata

    def _get_class_name(self, cursor):
        """Get class name for a method"""
        parent = cursor.semantic_parent
        if parent and parent.kind in [CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL, CursorKind.CLASS_TEMPLATE]:
            return parent.spelling
        return None

    def _get_namespace(self, cursor):
        """Get namespace for a cursor"""
        parent = cursor.semantic_parent
        if parent and parent.kind == CursorKind.NAMESPACE:
            return parent.spelling
        return None

    def _get_function_extent(self, cursor):
        """Get the source range of a function definition"""
        # Get the source range
        start = cursor.extent.start
        end = cursor.extent.end
        
        # Get source file
        file = start.file.name
        
        # Get line numbers
        start_line = start.line
        end_line = end.line
        
        return file, start_line, end_line

    def extract_cpp_functions(self, cpp_file, header_functions, function_metadata):
        """Extract function implementations from cpp file"""
        # Parse the cpp file
        tu = self.index.parse(cpp_file, args=self.compilation_flags)
        
        functions = []
        
        # Read the file content
        with open(cpp_file, 'r') as f:
            file_content = f.read()
            file_lines = file_content.splitlines(True)  # Keep line endings
        
        # Get the absolute path of the cpp file for comparison
        cpp_file_abs = os.path.abspath(cpp_file)
        
        # Create a set of function names from the header for pre-filtering
        header_function_names = set()
        for sig, name in header_functions.items():
            # Store both fully qualified and simple names
            header_function_names.add(name)
            simple_name = name.split('::')[-1]
            header_function_names.add(simple_name)
        
        # Visit all function definitions in the cpp file
        for cursor in tu.cursor.walk_preorder():
            try:
                # Safely check cursor kind
                if cursor.kind not in [CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD, 
                                    CursorKind.CONSTRUCTOR, CursorKind.DESTRUCTOR]:
                    continue  # Skip unknown or irrelevant kinds
                    
                # Skip if this is not a definition
                if not cursor.is_definition():
                    continue
                
                # Skip if the function is not from the current file
                if cursor.location.file is None or os.path.abspath(cursor.location.file.name) != cpp_file_abs:
                    continue
                
                # Get function name and check if it's in the header
                qualified_name = self._get_fully_qualified_name(cursor)
                simple_name = qualified_name.split('::')[-1]
                
                # Skip if the function name doesn't match any function in the header
                if qualified_name not in header_function_names and simple_name not in header_function_names:
                    continue
                
                # Get function extent
                file_path, start_line, end_line = self._get_function_extent(cursor)
                
                # Skip if the line numbers are invalid or outside the file's range
                if start_line <= 0 or end_line <= 0 or start_line > len(file_lines) or end_line > len(file_lines):
                    continue
                
                # Get the actual function text from the file
                func_text_from_file = ''.join(file_lines[start_line-1:end_line])
                
                # Skip if the function text is empty or just whitespace
                if not func_text_from_file.strip():
                    continue
                
                # Verify this is a real function in our file by checking for a function body
                if '{' not in func_text_from_file or '}' not in func_text_from_file:
                    continue
                
                # Get function signature
                signature = self.get_function_signature(cursor)
                
                # Find matching header function
                header_sig = self._find_matching_header_function(signature, qualified_name, header_functions)
                
                # Only process functions that have a matching declaration in the header
                if header_sig:
                    # Get function text
                    func_text = func_text_from_file
                    
                    # Get access modifier from metadata
                    access_modifier = None
                    if header_sig in function_metadata:
                        access_modifier = function_metadata[header_sig].get("access")
                    
                    # Get comment
                    comment = self._get_comment(cursor)
                    
                    # If there's a comment in the header but not in the cpp, use the header comment
                    if not comment and header_sig in function_metadata and function_metadata[header_sig].get("comment"):
                        comment = function_metadata[header_sig].get("comment")
                    
                    # Add comment to function text if available
                    if comment:
                        func_text = comment + "\n" + func_text
                    
                    # Create function info
                    func_info = FunctionInfo(
                        name=qualified_name,
                        signature=header_sig,
                        full_text=func_text,
                        index=start_line-1,  # 0-based index
                        access_modifier=access_modifier
                    )
                    
                    functions.append(func_info)
            
            except ValueError as e:
                print(f"Warning: Skipping cursor due to unknown kind: {e}")
                continue
        
        return functions

    def _find_matching_header_function(self, cpp_signature, cpp_name, header_functions):
        """Find matching header function for cpp implementation"""
        # Try direct match first
        if cpp_signature in header_functions:
            return cpp_signature
        
        # Try matching by name
        for header_sig, header_name in header_functions.items():
            if header_name == cpp_name:
                return header_sig
            
            # Extract simple name from qualified names
            cpp_simple_name = cpp_name.split('::')[-1]
            header_simple_name = header_name.split('::')[-1]
            
            if cpp_simple_name == header_simple_name:
                # Compare parameter types (already part of the signature)
                cpp_params = cpp_signature.split('(')[1].split(')')[0]
                header_params = header_sig.split('(')[1].split(')')[0]
                
                if self._normalize_params(cpp_params) == self._normalize_params(header_params):
                    return header_sig
        
        return None

    def _normalize_params(self, params_str):
        """Normalize parameter string to help with matching"""
        # Split parameters
        if not params_str:
            return ""
            
        params = params_str.split(',')
        
        # Remove qualifiers that might differ between declaration and definition
        normalized_params = []
        for param in params:
            # Remove const, volatile, etc.
            param = param.replace("const ", "").replace("volatile ", "")
            normalized_params.append(param.strip())
        
        return ','.join(normalized_params)

    def reorder_cpp_content(self, cpp_file, function_order, functions, function_metadata, log_func=None):
        """Reorder functions in the cpp content based on header order"""
        # Read the file content
        with open(cpp_file, 'r') as f:
            cpp_content = f.read()
            lines = cpp_content.split('\n')
        
        if log_func:
            log_func("\n--- Function Reordering Analysis ---")
            
        
        # Sort functions according to their order in the header file
        # First by access modifier (public, protected, private), then by header order
        def sort_key(func):
            access_priority = {"public": 0, "protected": 1, "private": 2, None: 3}
            access_value = access_priority.get(func.access_modifier, 3)
            order_value = function_order.get(func.signature, float('inf'))
            return (access_value, order_value)
        
        sorted_functions = sorted(functions, key=sort_key)
        
        if log_func:
            log_func("\nFunction order in the .h file (desired order):")
            for sig, order in sorted(function_order.items(), key=lambda item: item[1]):
                access = "N/A"
                if sig in function_metadata:
                    access = function_metadata[sig].get("access", "N/A")
                log_func(f"  - {sig} (Order: {order}, Access: {access})")
            
            log_func("\nReordered function order in the .cpp file:")
            for func in sorted_functions:
                log_func(f"  - {func.signature} (Access: {func.access_modifier})")
            log_func("--- End of Function Reordering Analysis ---\n")
        
        # Find blocks of code for each function
        blocks = []
        marked_lines = set()
        
        # Get function extents
        for func in functions:
            # Find the start and end of the function in the file
            start_line = func.index
            
            # Find the end of the function by counting braces
            brace_count = 0
            end_line = start_line
            
            # Look for comments before the function
            j = start_line - 1
            # Fix: Check if j is valid before accessing lines[j]
            while j >= 0 and j < len(lines) and (lines[j].strip().startswith("//") or lines[j].strip() == ""):
                if lines[j].strip().startswith("//"):
                    start_line = j
                j -= 1
            
            # Find the end of the function
            for i in range(start_line, len(lines)):
                line = lines[i]
                brace_count += line.count('{')
                brace_count -= line.count('}')
                end_line = i
                
                if brace_count == 0 and i > start_line:  # Make sure we've seen at least one opening brace
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
    parser.add_argument('--log', action='store_true', help='Enable detailed logging')

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

    # Create parser
    parser = ClangCppParser()
    
    # Log function
    log_func = print if args.log else None

    try:
        # Extract functions from header file
        header_functions, function_metadata = parser.extract_header_functions(args.header)

        if not header_functions:
            print("Warning: No function declarations found in header file")

        # Create an order mapping for header functions
        function_order = {sig: i for i, sig in enumerate(header_functions.keys())}

        # Extract functions from implementation file
        cpp_functions = parser.extract_cpp_functions(args.implementation, header_functions, function_metadata)

        if not cpp_functions:
            print("Warning: No function implementations found in source file")
            return 0

        # Reorder implementation functions
        reordered_content = parser.reorder_cpp_content(args.implementation, function_order, cpp_functions, function_metadata, log_func)

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
        if args.log:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    # Check if running in GUI or CLI mode
    if len(sys.argv) > 1:
        sys.exit(main())
    else:
        try:
            from main import run_gui
            run_gui()
        except ImportError:
            print("GUI mode not available. Please provide command line arguments.")
            print("Use --help for usage information.")
            sys.exit(1)
