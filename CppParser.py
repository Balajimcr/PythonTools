#!/usr/bin/env python3
"""
C++ Function Layout Tool

This script rearranges functions in C++ header (.h) and source (.cpp) files
according to a defined layout configuration. It helps maintain consistent 
code organization and improves readability.
"""

import os
import sys
import argparse
import json
import re
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Set

# Import libclang
import clang.cindex
from clang.cindex import Index, CursorKind, TokenKind

class FunctionDefinition:
    """Stores information about a C++ function definition or declaration"""
    def __init__(self, name, signature, line_start, line_end, full_text, 
                 access_specifier=None, class_name=None, namespace=None, is_static=False):
        self.name = name                      # Function name
        self.signature = signature            # Full function signature for matching
        self.line_start = line_start          # Starting line in the file
        self.line_end = line_end              # Ending line in the file
        self.full_text = full_text            # Complete text of the function
        self.access_specifier = access_specifier  # public, protected, private
        self.class_name = class_name          # Class name if method
        self.namespace = namespace            # Namespace
        self.is_static = is_static            # Is it a static function/method

    def __str__(self):
        return (f"FunctionDefinition(name={self.name}, "
                f"class={self.class_name}, "
                f"access={self.access_specifier}, "
                f"lines={self.line_start}-{self.line_end})")

class LayoutRule:
    """Defines a rule for arranging functions"""
    def __init__(self, priority, criteria):
        self.priority = priority  # Lower number = higher priority
        self.criteria = criteria  # Dict of criteria to match (e.g., {"access": "public", "is_static": True})

    def matches(self, func_def):
        """Check if a function definition matches this rule's criteria"""
        for key, value in self.criteria.items():
            if key == "access" and getattr(func_def, "access_specifier", None) != value:
                return False
            elif key == "is_static" and getattr(func_def, "is_static", False) != value:
                return False
            elif key == "class" and getattr(func_def, "class_name", None) != value:
                return False
            elif key == "namespace" and getattr(func_def, "namespace", None) != value:
                return False
            elif key == "name_pattern":
                pattern = re.compile(value)
                if not pattern.search(func_def.name):
                    return False
        return True

class ClangCppParser:
    """Parser for C++ files using libclang"""
    def __init__(self, layout_config=None):
        self._setup_clang()
        self.layout_rules = self._load_layout_rules(layout_config)
        
    def _setup_clang(self):
        """Setup libclang with appropriate paths"""
        from clang.cindex import Config, Index
        
        # Log libclang version
        try:
            version = clang.cindex.conf.lib.clang_getClangVersion().decode()
            print(f"Using libclang version: {version}")
        except Exception as e:
            print(f"Could not determine libclang version: {e}")
        
        # List of possible libclang paths
        possible_paths = [
            "C:/Program Files/LLVM/bin/libclang.dll",
            os.path.expanduser("~/LLVM/bin/libclang.dll"),
            "/usr/lib/llvm-10/lib/libclang.so",  # Ubuntu/Debian
            "/usr/lib/llvm-10/lib/libclang.so.1",
            "/usr/local/opt/llvm/lib/libclang.dylib",  # macOS
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
        
        self.index = Index.create()
        self.compilation_flags = [
            '-x', 'c++',
            '-std=c++20',  # Updated to C++20 for better modern feature support
            '-fparse-all-comments'
        ]

    def _load_layout_rules(self, config_file):
        """Load layout rules from a configuration file or use defaults"""
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    rules_data = json.load(f)
                return [LayoutRule(rule["priority"], rule["criteria"]) 
                        for rule in rules_data["rules"]]
            except Exception as e:
                print(f"Error loading layout config: {e}")
                print("Using default layout rules")
        
        # Default rules
        return [
            # Public methods first
            LayoutRule(10, {"access": "public"}),
            # Protected methods second
            LayoutRule(20, {"access": "protected"}),
            # Private methods last
            LayoutRule(30, {"access": "private"}),
            # Static methods within each access group come first
            LayoutRule(5, {"is_static": True}),
            # Constructor/Destructor pattern comes early in each section
            LayoutRule(3, {"name_pattern": r"(^~?\w+$|constructor|destructor)"}),
        ]

    def get_function_signature(self, cursor):
        """Create a unique signature for a function"""
        qualified_name = self._get_fully_qualified_name(cursor)
        param_types = [param.type.spelling for param in cursor.get_arguments()]
        return_type = cursor.result_type.spelling
        return f"{return_type} {qualified_name}({','.join(param_types)})"

    def _get_fully_qualified_name(self, cursor):
        """Get fully qualified name of a cursor including namespaces and classes"""
        if cursor is None or cursor.kind == CursorKind.TRANSLATION_UNIT:
            return ""
        parent = self._get_fully_qualified_name(cursor.semantic_parent)
        return f"{parent}::{cursor.spelling}" if parent else cursor.spelling

    def _get_access_specifier(self, cursor):
        """Get access specifier (public, private, protected) for a cursor"""
        if cursor.access_specifier == clang.cindex.AccessSpecifier.PUBLIC:
            return "public"
        elif cursor.access_specifier == clang.cindex.AccessSpecifier.PROTECTED:
            return "protected"
        elif cursor.access_specifier == clang.cindex.AccessSpecifier.PRIVATE:
            return "private"
        return None

    def _is_static_function(self, cursor):
        """Check if function is static"""
        for token in cursor.get_tokens():
            if token.spelling == 'static':
                return True
        return False

    def _get_comment(self, cursor):
        """Get comment associated with a cursor"""
        comment = cursor.brief_comment or ""
        if comment and not all(line.strip().startswith('//') for line in comment.split('\n') if line.strip()):
            comment = '\n'.join([f"// {line}" for line in comment.split('\n')])
        return comment

    def _get_class_name(self, cursor):
        """Get class name for a method"""
        parent = cursor.semantic_parent
        if parent and parent.kind in [CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL, CursorKind.CLASS_TEMPLATE]:
            return parent.spelling
        return None

    def _get_namespace(self, cursor):
        """Get namespace for a cursor"""
        namespaces = []
        parent = cursor.semantic_parent
        while parent and parent.kind != CursorKind.TRANSLATION_UNIT:
            if parent.kind == CursorKind.NAMESPACE:
                namespaces.insert(0, parent.spelling)
            parent = parent.semantic_parent
        return "::".join(namespaces) if namespaces else None

    def parse_header_file(self, header_file):
        """Parse a header file and extract function declarations"""
        try:
            tu = self.index.parse(header_file, args=self.compilation_flags)
            functions = {}
            function_order = {}
            index = 0
            
            for cursor in tu.cursor.walk_preorder():
                try:
                    if cursor.kind not in [CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD, 
                                           CursorKind.CONSTRUCTOR, CursorKind.DESTRUCTOR]:
                        continue
                    if cursor.is_definition():
                        continue
                    
                    signature = self.get_function_signature(cursor)
                    name = cursor.spelling
                    start_loc = cursor.extent.start
                    end_loc = cursor.extent.end
                    start_line = start_loc.line
                    end_line = end_loc.line
                    comment = self._get_comment(cursor)
                    access_spec = self._get_access_specifier(cursor)
                    class_name = self._get_class_name(cursor)
                    namespace = self._get_namespace(cursor)
                    is_static = self._is_static_function(cursor)
                    
                    func_def = FunctionDefinition(
                        name=name,
                        signature=signature,
                        line_start=start_line,
                        line_end=end_line,
                        full_text="",
                        access_specifier=access_spec,
                        class_name=class_name,
                        namespace=namespace,
                        is_static=is_static
                    )
                    
                    functions[signature] = func_def
                    function_order[signature] = index
                    index += 1
                except ValueError as ve:
                    print(f"Skipping cursor due to unknown kind {cursor._kind_id} at {cursor.location}: {ve}")
                    continue
            
            return functions, function_order
        except Exception as e:
            print(f"Error parsing header file: {e}")
            raise

    def parse_source_file(self, source_file, header_functions):
        """Parse a source file and extract function definitions"""
        try:
            tu = self.index.parse(source_file, args=self.compilation_flags)
            with open(source_file, 'r') as f:
                source_lines = f.read().splitlines(True)
            functions = []
            source_file_abs = os.path.abspath(source_file)
            
            for cursor in tu.cursor.walk_preorder():
                try:
                    if cursor.kind not in [CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD, 
                                           CursorKind.CONSTRUCTOR, CursorKind.DESTRUCTOR]:
                        continue
                    if not cursor.is_definition():
                        continue
                    if cursor.location.file is None or os.path.abspath(cursor.location.file.name) != source_file_abs:
                        continue
                    
                    signature = self.get_function_signature(cursor)
                    name = cursor.spelling
                    header_sig = self._find_matching_header_function(signature, name, header_functions)
                    if not header_sig:
                        continue
                    
                    header_func = header_functions[header_sig]
                    start_loc = cursor.extent.start
                    end_loc = cursor.extent.end
                    start_line = start_loc.line - 1
                    end_line = end_loc.line - 1
                    
                    if start_line < 0 or end_line >= len(source_lines):
                        continue
                    
                    comment_start = start_line
                    j = start_line - 1
                    while j >= 0 and (source_lines[j].strip().startswith("//") or 
                                     source_lines[j].strip().startswith("/*") or 
                                     source_lines[j].strip() == ""):
                        comment_start = j
                        j -= 1
                    
                    func_text = ''.join(source_lines[comment_start:end_line+1])
                    func_def = FunctionDefinition(
                        name=name,
                        signature=header_sig,
                        line_start=comment_start,
                        line_end=end_line,
                        full_text=func_text,
                        access_specifier=header_func.access_specifier,
                        class_name=header_func.class_name,
                        namespace=header_func.namespace,
                        is_static=header_func.is_static
                    )
                    functions.append(func_def)
                except ValueError as ve:
                    print(f"Skipping cursor due to unknown kind {cursor._kind_id} at {cursor.location}: {ve}")
                    continue
            
            return functions
        except Exception as e:
            print(f"Error parsing source file: {e}")
            raise

    def _find_matching_header_function(self, cpp_signature, cpp_name, header_functions):
        """Find matching header function for cpp implementation"""
        for header_sig, header_func in header_functions.items():
            if self._normalize_signature(cpp_signature) == self._normalize_signature(header_sig):
                return header_sig
            if header_func.name == cpp_name:
                cpp_params = self._extract_parameters(cpp_signature)
                header_params = self._extract_parameters(header_sig)
                if self._compare_parameter_lists(cpp_params, header_params):
                    return header_sig
        return None

    def _normalize_signature(self, signature):
        """Normalize a function signature for comparison"""
        normalized = re.sub(r'\s*::\s*', '::', signature)
        normalized = re.sub(r'\s*\(\s*', '(', normalized)
        normalized = re.sub(r'\s*\)\s*', ')', normalized)
        normalized = re.sub(r'\s*,\s*', ',', normalized)
        normalized = re.sub(r'\bconst\b', '', normalized)
        normalized = re.sub(r'\bvolatile\b', '', normalized)
        return normalized.strip()

    def _extract_parameters(self, signature):
        """Extract parameter list from a function signature"""
        match = re.search(r'\((.*)\)', signature)
        return match.group(1) if match else ""

    def _compare_parameter_lists(self, params1, params2):
        """Compare two parameter lists for functional equivalence"""
        if not params1 and not params2:
            return True
        params1_list = params1.split(',') if params1 else []
        params2_list = params2.split(',') if params2 else []
        if len(params1_list) != len(params2_list):
            return False
        for p1, p2 in zip(params1_list, params2_list):
            if not self._are_equivalent_types(p1.strip(), p2.strip()):
                return False
        return True

    def _are_equivalent_types(self, type1, type2):
        """Check if two parameter types are equivalent"""
        type1 = re.sub(r'\bconst\b', '', type1).strip()
        type2 = re.sub(r'\bconst\b', '', type2).strip()
        type1 = re.sub(r'\bvolatile\b', '', type1).strip()
        type2 = re.sub(r'\bvolatile\b', '', type2).strip()
        type1 = re.sub(r'\s+\w+$', '', type1).strip()
        type2 = re.sub(r'\s+\w+$', '', type2).strip()
        return type1 == type2

    def reorder_functions(self, source_file, source_functions, header_order):
        """Reorder functions in the source file according to the layout rules and header order"""
        with open(source_file, 'r') as f:
            source_lines = f.read().splitlines(True)
        
        def sort_key(func):
            priority = 1000
            for rule in self.layout_rules:
                if rule.matches(func):
                    priority = min(priority, rule.priority)
            order = header_order.get(func.signature, float('inf'))
            return (priority, order)
        
        sorted_functions = sorted(source_functions, key=sort_key)
        function_blocks = set()
        for func in source_functions:
            for i in range(func.line_start, func.line_end + 1):
                function_blocks.add(i)
        
        non_function_blocks = []
        current_block = []
        for i, line in enumerate(source_lines):
            if i in function_blocks:
                if current_block:
                    non_function_blocks.append((current_block[0], current_block[-1], ''.join(current_block)))
                    current_block = []
            else:
                current_block.append(line)
        
        if current_block:
            non_function_blocks.append((len(source_lines) - len(current_block), len(source_lines) - 1, ''.join(current_block)))
        
        new_content = []
        if non_function_blocks and non_function_blocks[0][0] == 0:
            new_content.append(non_function_blocks[0][2])
            non_function_blocks.pop(0)
        
        for func in sorted_functions:
            new_content.append(func.full_text)
        
        for _, _, block_text in non_function_blocks:
            new_content.append(block_text)
        
        return ''.join(new_content)

def main():
    """Main entry point for the command-line interface"""
    parser = argparse.ArgumentParser(
        description='Reorder C++ functions in header and source files according to layout rules'
    )
    parser.add_argument('header', help='Path to the header file (.h/.hpp)')
    parser.add_argument('source', help='Path to the source file (.cpp/.cc)')
    parser.add_argument('-o', '--output', help='Output file (defaults to overwriting source file)')
    parser.add_argument('-c', '--config', help='Path to layout rules configuration file (JSON)')
    parser.add_argument('--dry-run', action='store_true', help='Print result without writing to file')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    if not args.header.endswith(('.h', '.hpp')):
        print(f"Error: Header file should have .h or .hpp extension: {args.header}")
        return 1
        
    if not args.source.endswith(('.cpp', '.cc')):
        print(f"Error: Source file should have .cpp or .cc extension: {args.source}")
        return 1
    
    if not os.path.isfile(args.header):
        print(f"Error: Header file not found: {args.header}")
        return 1
        
    if not os.path.isfile(args.source):
        print(f"Error: Source file not found: {args.source}")
        return 1
    
    try:
        parser = ClangCppParser(args.config)
        if args.verbose:
            print(f"Parsing header file: {args.header}")
        
        header_functions, function_order = parser.parse_header_file(args.header)
        if args.verbose:
            print(f"Found {len(header_functions)} function declarations in header")
            for sig, func in header_functions.items():
                print(f"  - {func.name} (Access: {func.access_specifier}, Static: {func.is_static})")
        
        if not header_functions:
            print("Warning: No function declarations found in header file")
        
        if args.verbose:
            print(f"Parsing source file: {args.source}")
        
        source_functions = parser.parse_source_file(args.source, header_functions)
        if args.verbose:
            print(f"Found {len(source_functions)} function implementations in source")
            for func in source_functions:
                print(f"  - {func.name} (Lines: {func.line_start+1}-{func.line_end+1})")
        
        if not source_functions:
            print("Warning: No function implementations found in source file")
            return 0
        
        if args.verbose:
            print("Reordering functions according to layout rules")
        
        reordered_content = parser.reorder_functions(args.source, source_functions, function_order)
        
        if args.dry_run:
            print(reordered_content)
            print("Dry run completed. No files were modified.")
        else:
            output_file = args.output or args.source
            with open(output_file, 'w') as f:
                f.write(reordered_content)
            print(f"Successfully reordered functions in {output_file}")
        
        return 0
    except Exception as e:
        print(f"Error processing files: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(main())
    else:
        try:
            from gui import run_gui
            run_gui()
        except ImportError:
            print("GUI mode not available. Please provide command line arguments.")
            print("Use --help for usage information.")
            sys.exit(1)
