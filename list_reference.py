import os

ref_path = r'C:\Users\ArsesMobile\Desktop\New folder (2)'

print("=" * 60)
print("REFERENCE IMPLEMENTATION STRUCTURE")
print("=" * 60)
print(f"Path: {ref_path}\n")

for root, dirs, files in os.walk(ref_path):
    level = root.replace(ref_path, '').count(os.sep)
    indent = '  ' * level
    print(f"{indent}{os.path.basename(root)}/")
    subindent = '  ' * (level + 1)
    for file in files[:10]:  # Limit to first 10 files per dir
        print(f"{subindent}{file}")
    if len(files) > 10:
        print(f"{subindent}... and {len(files) - 10} more files")
