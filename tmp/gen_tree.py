
import os

def print_tree(startpath, max_depth=3):
    for root, dirs, files in os.walk(startpath):
        level = root.replace(startpath, '').count(os.sep)
        if level > max_depth:
            continue
        indent = ' ' * 4 * (level)
        print('{}{}/'.format(indent, os.path.basename(root)))
        subindent = ' ' * 4 * (level + 1)
        # Limit files to show
        if level < max_depth:
            for f in files[:20]: # Show first 20 files
                print('{}{}'.format(subindent, f))
            if len(files) > 20:
                print('{}(... {} more files)'.format(subindent, len(files) - 20))

if __name__ == "__main__":
    print_tree(os.getcwd())
