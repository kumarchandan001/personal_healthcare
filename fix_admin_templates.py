import os
import shutil

# Define template directories
templates_dir = 'templates'

# Create copies with consistent naming
template_mappings = {
    'admin_login.html': 'direct_admin_login.html',
    'admin_dashboard.html': 'direct_admin_dashboard.html',
    'admin_users.html': 'direct_admin_users.html',
    'admin_user_history.html': 'user_history.html'
}

# Make sure templates directory exists
if not os.path.exists(templates_dir):
    os.makedirs(templates_dir)
    print(f"Created directory: {templates_dir}")

for source, target in template_mappings.items():
    source_path = os.path.join(templates_dir, source)
    target_path = os.path.join(templates_dir, target)
    
    # If both exist, copy source to target to ensure they match
    if os.path.exists(source_path) and os.path.exists(target_path):
        print(f"Both {source} and {target} exist. Updating {target} to match {source}...")
        shutil.copy2(source_path, target_path)
    
    # If only source exists, create target as a copy
    elif os.path.exists(source_path) and not os.path.exists(target_path):
        print(f"Copying {source} to {target}...")
        shutil.copy2(source_path, target_path)
    
    # If only target exists, create source as a copy
    elif not os.path.exists(source_path) and os.path.exists(target_path):
        print(f"Copying {target} to {source}...")
        shutil.copy2(target_path, source_path)
    
    # If neither exists, print warning
    else:
        print(f"Warning: Neither {source} nor {target} exists.")

print("Template synchronization complete.") 