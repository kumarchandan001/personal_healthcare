import os
import subprocess
import sys

def run_script(script_name):
    print(f"Running {script_name}...")
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
    try:
        result = subprocess.run(['python', script_path], check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_name}: {e}")
        return False

def setup_admin():
    print("="*60)
    print("HEALTH ASSISTANT ADMIN PANEL SETUP")
    print("="*60)
    
    # Step 1: Create/update database
    print("\nStep 1: Setting up database...")
    if not run_script('create_db.py'):
        print("ERROR: Failed to setup database!")
        return False
    
    # Step 2: Add sample data if needed
    add_sample = input("\nDo you want to add sample data? (y/n): ").lower().strip()
    if add_sample == 'y':
        print("\nStep 2: Adding sample data...")
        if not run_script('add_sample_data.py'):
            print("WARNING: Failed to add sample data, but continuing...")
    else:
        print("\nSkipping sample data...")
    
    # Step 3: Fix template files
    print("\nStep 3: Fixing admin templates...")
    if not run_script('fix_admin_templates.py'):
        print("WARNING: Failed to fix templates, but continuing...")
    
    print("\nSetup completed successfully!")
    print("\nYou can now start the admin panel by running:")
    print("  python start_admin_panel.py")
    print("\nCredentials:")
    print("  Username: admin")
    print("  Password: admin123")
    print("="*60)
    
    start_now = input("\nDo you want to start the admin panel now? (y/n): ").lower().strip()
    if start_now == 'y':
        print("\nStarting admin panel...")
        run_script('start_admin_panel.py')
    
    return True

if __name__ == "__main__":
    setup_admin() 