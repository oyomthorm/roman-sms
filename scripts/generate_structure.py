import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Define folders to skip
SKIP_FOLDERS = {'__pycache__', '.git', 'node_modules', '.venv', 'venv', '__pycache__', '.idea', '.vscode'}

def should_skip_folder(folder_name):
    """Check if a folder should be skipped"""
    return folder_name in SKIP_FOLDERS

def generate_file_structure(root_dir, indent='', prefix='', show_files=True, max_depth=None, current_depth=0, show_icons=True):
    """
    Generate and print file structure recursively to console
    
    Args:
        root_dir: Root directory path
        indent: Current indentation string
        prefix: Prefix for tree structure (├──, └──, │)
        show_files: Whether to show files or only directories
        max_depth: Maximum depth to traverse (None for unlimited)
        current_depth: Current recursion depth
        show_icons: Whether to show folder/file icons
    """
    if max_depth is not None and current_depth > max_depth:
        return
    
    try:
        entries = sorted(os.listdir(root_dir))
    except PermissionError:
        folder_icon = "⚠️ " if show_icons else ""
        print(f"{indent}{prefix}{folder_icon}Permission Denied: {os.path.basename(root_dir)}")
        return
    except FileNotFoundError:
        print(f"❌ Error: Directory '{root_dir}' not found")
        return
    
    # Separate directories and files - SKIP specified folders
    dirs = []
    files = []
    
    for entry in entries:
        full_path = os.path.join(root_dir, entry)
        if os.path.isdir(full_path):
            # Skip folders like __pycache__
            if not should_skip_folder(entry):
                dirs.append(entry)
        else:
            files.append(entry)
    
    # Process directories
    for i, dir_name in enumerate(dirs):
        is_last = (i == len(dirs) - 1 and (not show_files or not files))
        new_prefix = '└── ' if is_last else '├── '
        new_indent = indent + ('    ' if is_last else '│   ')
        
        folder_icon = "📁 " if show_icons else ""
        print(f"{indent}{new_prefix}{folder_icon}{dir_name}/")
        
        full_path = os.path.join(root_dir, dir_name)
        generate_file_structure(
            full_path, 
            new_indent, 
            '', 
            show_files, 
            max_depth, 
            current_depth + 1,
            show_icons
        )
    
    # Process files
    if show_files:
        for i, file_name in enumerate(files):
            is_last = (i == len(files) - 1)
            new_prefix = '└── ' if is_last else '├── '
            
            # Get file info
            try:
                file_path = os.path.join(root_dir, file_name)
                size = os.path.getsize(file_path)
                size_str = f" ({format_size(size)})"
                
                # Get file extension icon
                ext = os.path.splitext(file_name)[1].lower()
                file_icon = get_file_icon(ext) if show_icons else "📄 "
            except:
                size_str = ""
                file_icon = "📄 " if show_icons else ""
            
            print(f"{indent}{new_prefix}{file_icon}{file_name}{size_str}")

def get_file_icon(extension):
    """Return an icon based on file extension"""
    icons = {
        '.py': '🐍 ',
        '.js': '🟨 ',
        '.html': '🌐 ',
        '.css': '🎨 ',
        '.json': '📋 ',
        '.xml': '📋 ',
        '.yaml': '📋 ',
        '.yml': '📋 ',
        '.md': '📝 ',
        '.txt': '📄 ',
        '.pdf': '📕 ',
        '.jpg': '🖼️ ',
        '.jpeg': '🖼️ ',
        '.png': '🖼️ ',
        '.gif': '🖼️ ',
        '.svg': '🖼️ ',
        '.mp3': '🎵 ',
        '.wav': '🎵 ',
        '.mp4': '🎬 ',
        '.avi': '🎬 ',
        '.mov': '🎬 ',
        '.zip': '📦 ',
        '.rar': '📦 ',
        '.tar': '📦 ',
        '.gz': '📦 ',
        '.exe': '⚙️ ',
        '.sh': '💻 ',
        '.bat': '💻 ',
        '.ps1': '💻 ',
    }
    return icons.get(extension, '📄 ')

def format_size(size):
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}PB"

def generate_structure_text(root_dir, show_files=True, max_depth=None, show_icons=True):
    """Generate file structure as text string - SKIPS __pycache__ folders"""
    result = []
    
    def collect_structure(dir_path, indent='', prefix='', depth=0):
        if max_depth is not None and depth > max_depth:
            return
        
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            result.append(f"{indent}{prefix}⚠️ Permission Denied: {os.path.basename(dir_path)}")
            return
        
        dirs = []
        files = []
        
        for entry in entries:
            full_path = os.path.join(dir_path, entry)
            if os.path.isdir(full_path):
                # Skip folders like __pycache__
                if not should_skip_folder(entry):
                    dirs.append(entry)
            else:
                files.append(entry)
        
        # Process directories
        for i, dir_name in enumerate(dirs):
            is_last = (i == len(dirs) - 1 and (not show_files or not files))
            new_prefix = '└── ' if is_last else '├── '
            new_indent = indent + ('    ' if is_last else '│   ')
            
            folder_icon = "📁 " if show_icons else ""
            result.append(f"{indent}{new_prefix}{folder_icon}{dir_name}/")
            
            full_path = os.path.join(dir_path, dir_name)
            collect_structure(full_path, new_indent, '', depth + 1)
        
        # Process files
        if show_files:
            for i, file_name in enumerate(files):
                is_last = (i == len(files) - 1)
                new_prefix = '└── ' if is_last else '├── '
                
                if show_icons:
                    ext = os.path.splitext(file_name)[1].lower()
                    file_icon = get_file_icon(ext)
                else:
                    file_icon = ""
                
                result.append(f"{indent}{new_prefix}{file_icon}{file_name}")
    
    collect_structure(root_dir)
    return '\n'.join(result)

def save_structure_to_file(root_dir, output_file, show_files=True, max_depth=None, show_icons=True):
    """
    Save file structure to a text file - SKIPS __pycache__ folders
    """
    try:
        # Generate the structure
        structure = generate_structure_text(root_dir, show_files, max_depth, show_icons)
        
        # Write to file with header information
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write(f"📁 FILE STRUCTURE GENERATOR\n")
            f.write("=" * 60 + "\n")
            f.write(f"Root Directory: {os.path.abspath(root_dir)}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Show Files: {show_files}\n")
            f.write(f"Skipped Folders: {', '.join(SKIP_FOLDERS)}\n")
            if max_depth:
                f.write(f"Max Depth: {max_depth}\n")
            f.write("=" * 60 + "\n\n")
            f.write(structure)
            f.write("\n\n" + "=" * 60 + "\n")
            f.write("End of Structure\n")
        
        print(f"✅ File structure successfully saved to: {output_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error saving to file: {e}")
        return False

def get_directory_stats(root_dir):
    """Get statistics about the directory - SKIPS __pycache__ folders"""
    total_files = 0
    total_dirs = 0
    total_size = 0
    
    for root, dirs, files in os.walk(root_dir):
        # Remove skipped folders from dirs list to prevent walking into them
        dirs[:] = [d for d in dirs if not should_skip_folder(d)]
        
        total_dirs += len(dirs)
        total_files += len(files)
        for file in files:
            try:
                total_size += os.path.getsize(os.path.join(root, file))
            except:
                pass
    
    return {
        'total_files': total_files,
        'total_dirs': total_dirs,
        'total_size': total_size,
        'total_size_human': format_size(total_size)
    }

def generate_tree_for_specific_extensions(root_dir, extensions=None):
    """Generate structure showing only specific file extensions - SKIPS __pycache__ folders"""
    if extensions is None:
        extensions = ['.py', '.js', '.html', '.css']
    
    def check_extension(file_name):
        ext = os.path.splitext(file_name)[1].lower()
        return ext in extensions
    
    def filtered_generate(dir_path, indent='', prefix='', depth=0):
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return
        
        dirs = []
        files = []
        
        for entry in entries:
            full_path = os.path.join(dir_path, entry)
            if os.path.isdir(full_path):
                # Skip folders like __pycache__
                if not should_skip_folder(entry):
                    dirs.append(entry)
            elif check_extension(entry):
                files.append(entry)
        
        for i, dir_name in enumerate(dirs):
            is_last = (i == len(dirs) - 1 and not files)
            new_prefix = '└── ' if is_last else '├── '
            new_indent = indent + ('    ' if is_last else '│   ')
            print(f"{indent}{new_prefix}📁 {dir_name}/")
            filtered_generate(os.path.join(dir_path, dir_name), new_indent, '', depth + 1)
        
        for i, file_name in enumerate(files):
            is_last = (i == len(files) - 1)
            new_prefix = '└── ' if is_last else '├── '
            print(f"{indent}{new_prefix}🐍 {file_name}")
    
    print(f"\n📂 FILE STRUCTURE (Only {', '.join(extensions)} files):\n")
    filtered_generate(root_dir)

def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(description='Generate file structure from a root folder')
    parser.add_argument('root', nargs='?', default='.', help='Root directory path (default: current directory)')
    parser.add_argument('-o', '--output', default='structure_2.txt', help='Output file name (default: structure_2.txt)')
    parser.add_argument('--no-files', action='store_true', help='Show only directories')
    parser.add_argument('--depth', type=int, help='Maximum depth to traverse')
    parser.add_argument('--no-icons', action='store_true', help='Hide icons in output')
    parser.add_argument('--filter', help='Filter by file extensions (comma-separated, e.g., .py,.js)')
    parser.add_argument('--stats-only', action='store_true', help='Show only statistics, not the full structure')
    parser.add_argument('--skip', help='Additional folders to skip (comma-separated)')
    
    args = parser.parse_args()
    
    # Add additional skip folders if specified
    if args.skip:
        additional_skips = [folder.strip() for folder in args.skip.split(',')]
        SKIP_FOLDERS.update(additional_skips)
    
    root = args.root
    show_files = not args.no_files
    show_icons = not args.no_icons
    max_depth = args.depth
    output_file = args.output
    
    # Check if directory exists
    if not os.path.exists(root):
        print(f"❌ Error: Directory '{root}' not found")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("📁 FILE STRUCTURE GENERATOR")
    print("=" * 60)
    
    # Get directory statistics
    stats = get_directory_stats(root)
    print(f"\n📊 Directory Statistics:")
    print(f"   • Total Files: {stats['total_files']}")
    print(f"   • Total Directories: {stats['total_dirs']}")
    print(f"   • Total Size: {stats['total_size_human']}")
    print(f"\n⏭️  Skipped Folders: {', '.join(SKIP_FOLDERS)}")
    
    if args.stats_only:
        print("\n" + "=" * 60)
        print("✅ Done!")
        sys.exit(0)
    
    # Handle filter option
    if args.filter:
        extensions = [ext.strip() for ext in args.filter.split(',')]
        generate_tree_for_specific_extensions(root, extensions)
    else:
        print("\n" + "-" * 60)
        
        # ========== PRINT TO CONSOLE ==========
        print("\n📂 FILE STRUCTURE:\n")
        generate_file_structure(root, show_files=show_files, max_depth=max_depth, show_icons=show_icons)
        
        # ========== SAVE TO FILE ==========
        print("\n" + "-" * 60)
        save_structure_to_file(root, output_file, show_files, max_depth, show_icons)
    
    print("\n" + "=" * 60)
    print("✅ Done!")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()