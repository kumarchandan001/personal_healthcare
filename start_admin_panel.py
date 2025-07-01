import os
import subprocess
import webbrowser

def start_admin_panel():
    print("="*60)
    print("STARTING ADMIN PANEL")
    print("="*60)
    print("The admin panel will be available at: http://127.0.0.1:5001")
    print("Use these credentials to log in:")
    print("  Username: admin")
    print("  Password: admin123")
    print("="*60)
    
    # Open the admin panel in the browser
    webbrowser.open('http://127.0.0.1:5001')
    
    # Start the admin panel application
    script_dir = os.path.dirname(os.path.abspath(__file__))
    admin_script = os.path.join(script_dir, 'admin_direct_access.py')
    
    # Run the admin panel
    subprocess.call(['python', admin_script])

if __name__ == "__main__":
    start_admin_panel() 