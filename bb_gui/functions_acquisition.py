import streamlit as st
import json
import os
import subprocess
import time

import psutil
import shutil

########################################################
# lock file for imgacquisition running
########################################################

LOCKFILE_PATH = "acquisition.lock"

def is_process_running(pid: int) -> bool:
    """Check if the process with given PID is still running."""
    return psutil.pid_exists(pid)

def read_lockfile() -> int | None:
    """Return PID from lockfile if it exists and is running, else remove lockfile."""
    if os.path.exists(LOCKFILE_PATH):
        try:
            with open(LOCKFILE_PATH, "r") as f:
                pid = int(f.read().strip())
            if is_process_running(pid):
                return pid
            else:
                os.remove(LOCKFILE_PATH)  # stale lockfile
        except:
            os.remove(LOCKFILE_PATH)
    return None

def write_lockfile(pid: int) -> None:
    """Write the PID to the lockfile."""
    with open(LOCKFILE_PATH, "w") as f:
        f.write(str(pid))

def remove_lockfile() -> None:
    """Remove the lockfile if present."""
    if os.path.exists(LOCKFILE_PATH):
        os.remove(LOCKFILE_PATH)



########################################################
# LOAD/SAVE CONFIG
########################################################
DEFAULT_CONFIG_PATH = os.path.expanduser("~/.config/bb_imgacquisition/config.json")

def load_config(config_path=DEFAULT_CONFIG_PATH):
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "_comment": "the config file should be located at ~/.config/bb_imgacquisition/config.json",
            "tmp_dir": "data/tmp",
            "out_dir": "data/out",
            "streams": {
                "cam-0": {
                    "camera": {
                        "backend": "basler",
                        "serial": "40562710",
                        "offset_x": 0,
                        "offset_y": 0,
                        "width": 5312,
                        "height": 4608,
                        "params": {
                            "offset_x": 0,
                            "offset_y": 0,
                            "width": 5312,
                            "height": 4608,
                            "trigger": {
                                "type": "software",
                                "frames_per_second": 6,
                                "source": 1
                            },
                            "bitrate": 1000000,
                            "rcmode": 0,
                            "qp": 24,
                            "brightness": 0,
                            "shutter": 3,
                            "gain": 22,
                            "exposure": 20000,
                            "whitebalance": 0
                        }
                    },
                    "frames_per_second": 6,
                    "frames_per_file": 360,
                }
            },
        }

def save_bbimg_config(config, config_path=DEFAULT_CONFIG_PATH):
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

########################################################
# ACQUISITION 
########################################################

def finalize_acquisition():
    """Actions after acquisition stops."""
    st.write("Finalizing acquisition...")
    config = load_config(config_path=DEFAULT_CONFIG_PATH)
    tmp_dir_ = config["tmp_dir"]
    out_dir_ = config["out_dir"]
    cam0 = list(streams.keys())[0]
    frames_per_file_ = config["streams"][cam0]["frames_per_file"]
    frames_per_second_ = config["streams"][cam0]["frames_per_second"]

    rename_and_move_temp_files(tmp_dir_, out_dir_, frames_per_file_, frames_per_second_, subdir=cam0)

    # Reset session state & remove lockfile
    remove_lockfile()
    st.session_state["acq_running"] = False
    st.session_state["acq_process"] = None
    st.session_state["acq_status"] = "Idle"
    st.success("Acquisition finished.")

def stop_acquisition():
    """Stop acquisition process via the PID in lockfile."""
    pid = read_lockfile()
    if pid:
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            proc.wait(timeout=5)
        except Exception as e:
            st.error(f"Failed to terminate process: {e}")

    finalize_acquisition()

def start_acquisition(command_path):
    """Start acquisition process and write to lockfile."""
    proc = subprocess.Popen([command_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pid = proc.pid
    write_lockfile(pid)

    st.session_state["acq_running"] = True
    st.session_state["acq_process"] = proc
    st.session_state["acq_status"] = "Running..."

def run_acquisition(tmp_dir, out_dir, frames_per_file, frames_per_second):
    """
    Streamlit-based acquisition with containers to show Start/Stop.
    Uses a lockfile to handle page refresh.
    """

    # Path to your acquisition script
    command_path = "/home/swarm/bb_imgacquisition/build/bb_imgacquisition"
    # For testing, fake script
    # command_path = "/Users/jacob/Library/CloudStorage/Dropbox/Bayer-Bees/Startup-cockroaches/gui/bb_imgacquisition_fake.sh"

    # 1) Check if a process is already running via lockfile
    existing_pid = read_lockfile()
    if existing_pid:
        st.session_state["acq_running"] = True
        st.session_state["acq_status"] = f"Running (PID {existing_pid})"

    # 2) Initialize session state if not defined
    if "acq_running" not in st.session_state:
        st.session_state["acq_running"] = False
    if "acq_process" not in st.session_state:
        st.session_state["acq_process"] = None
    if "acq_status" not in st.session_state:
        st.session_state["acq_status"] = "Idle"

    # 3) Container to display status & buttons
    status_container = st.container()
    with status_container:
        st.subheader(f"Status: {st.session_state['acq_status']}")

        button_container = st.container()
        if not st.session_state["acq_running"]:
            # Show Start button if not running
            if button_container.button("Start Acquisition", key="start_button"):
                start_acquisition(command_path)
                st.session_state["acq_running"] = True
                st.session_state["acq_status"] = "Running..."
                st.rerun()

        else:
            # If running, show Stop button
            if button_container.button("Stop Acquisition", key="stop_button"):
                stop_acquisition()
                st.session_state["acq_running"] = False
                st.session_state["acq_status"] = "Idle"
                st.rerun()

            # Check if process ended unexpectedly
            pid = read_lockfile()
            if pid is None:
                # Means the process ended on its own
                finalize_acquisition()
                st.rerun()

            # Optionally show a small auto-refresh for UI
            # e.g. st.info("Acquisition is running... refresh the page or check logs.")            

def rename_and_move_temp_files(tmp_dir, out_dir, frames_per_file, frames_per_second, subdir="cam-0"):
    """
    1. Finds .mp4 + .txt pairs in `tmp_dir/subdir` that were recently created
       (within the last (frames_per_file / frames_per_second) * 1.5 seconds).
    2. Parses the .txt file lines to get the first and last 'camera timestamps'.
    3. Renames both files to the Basler-style filename:
       e.g. cam-0_20250122T133601.562547.631Z--20250122T133611.395915.341Z.mp4/txt
    4. Moves the renamed files to `out_dir/subdir`.
    """
    
    tmp_dir_full = os.path.join(tmp_dir,subdir)
    
    # 1) Calculate the time threshold
    threshold_seconds = (frames_per_file / frames_per_second) * 1.5
    cutoff_time = time.time() - threshold_seconds

    # Ensure out_dir exists
    os.makedirs(out_dir, exist_ok=True)

    # We'll first gather all .txt files that were created/modified recently
    txt_files = [
        f for f in os.listdir(tmp_dir_full)
        if f.endswith(".txt")
    ]

    for txt_file in txt_files:
        txt_path = os.path.join(tmp_dir_full, txt_file)

        # Check the last modification time to see if it's within threshold
        mtime = os.path.getmtime(txt_path)
        if mtime < cutoff_time:
            # File not created/modified in our recent window => skip
            continue

        # 2) The .txt + .mp4 pair should share a base prefix,
        #    e.g. "segment123.txt" -> "segment123.mp4"
        base_name = os.path.splitext(txt_file)[0]  # "segment123"
        mp4_file = base_name + ".mp4"
        mp4_path = os.path.join(tmp_dir_full, mp4_file)

        if not os.path.exists(mp4_path):
            # No matching mp4 => skip
            continue

        # 3) Parse the .txt file lines to get first/last camera timestamps
        try:
            with open(txt_path, "r") as f:
                lines = [line.strip() for line in f if line.strip()]
            if not lines:
                # Empty or invalid file => skip
                continue

            first_ts = lines[0]   # First timestamp line
            last_ts = lines[-1]   # Last timestamp line

            # Ensure both timestamps start with "cam-X_"
            if "_" in first_ts and "_" in last_ts:
                cam_prefix, first_time_part = first_ts.split("_", 1)  # Split at first "_"
                _, last_time_part = last_ts.split("_", 1)  # Remove cam-0_ prefix from last

                # Construct the new filename in Basler format
                new_basename = f"{cam_prefix}_{first_time_part}--{last_time_part}"
                new_txt_name = new_basename + ".txt"
                new_mp4_name = new_basename + ".mp4"

            else:
                print(f"[ERROR] Invalid timestamp format in {txt_path}")
                continue

        except Exception as e:
            print(f"[ERROR] Failed to read lines from {txt_file}: {e}")
            continue

        # 4) Rename + move
        new_txt_path = os.path.join(out_dir, subdir, new_txt_name)
        new_mp4_path = os.path.join(out_dir, subdir, new_mp4_name)

        try:
            # Move (rename) the files to out_dir with the new names
            shutil.move(txt_path, new_txt_path)
            shutil.move(mp4_path, new_mp4_path)

            print(f"[INFO] Renamed & moved:\n"
                  f"  {txt_file} -> {new_txt_name}\n"
                  f"  {mp4_file} -> {new_mp4_name}")
        except Exception as e:
            print(f"[ERROR] Failed to move/rename {txt_file} or {mp4_file}: {e}")