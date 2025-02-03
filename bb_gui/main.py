import os
import sys
import subprocess

def main():
    """Launches the Streamlit app, forwarding all command-line arguments."""
    script_path = os.path.join(os.path.dirname(__file__), "bb_gui.py")

    # Construct the command by forwarding all arguments after "bb_gui"
    command = ["streamlit", "run", script_path] + sys.argv[1:]

    # Run the Streamlit command
    subprocess.run(command)

if __name__ == "__main__":
    main()