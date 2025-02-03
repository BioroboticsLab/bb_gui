import streamlit as st
import os
import glob
import pandas as pd
import functions_acquisition
import functions_data_and_pipeline
import urllib.parse

import importlib
importlib.reload(functions_acquisition)
importlib.reload(functions_data_and_pipeline)

def save_gui_config(config):
    # Implement your config saving here
    pass

def video_has_results(video_path, save_filetype, resultdir, detection_ext='-detections', tracks_ext='-tracks'):
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    detections_filename = os.path.join(resultdir, f"{base_name}{detection_ext}.{save_filetype}")
    has_detections = os.path.isfile(detections_filename) 

    tracks_filename = os.path.join(resultdir, f"{base_name}{tracks_ext}.{save_filetype}")
    has_tracks = os.path.isfile(tracks_filename)

    output_video_filename = os.path.join(resultdir, f"{base_name}-tracked-video.mp4")
    has_output_video = os.path.isfile(output_video_filename)
    return has_detections, has_tracks, has_output_video

def main():
    st.title("Beesbook recording and tracking")

    config = functions_acquisition.load_config()

    streams = config.get("streams", {})
    camera_names = list(streams.keys())
    if len(camera_names)>1:
        st.info("Multiple camera configuration detected. This is not currently supported for recording in bb_gui interface.")
        cam_name = 'cam-0'
        out_dir = os.path.abspath("out")  # default
    else:
        cam_name = camera_names[0]
        tmp_dir = st.text_input("Temporary Directory", value=config.get("tmp_dir", "tmp"))
        out_dir = st.text_input("Output Directory", value=config.get("out_dir", "out"))
        # convert to absolute paths for passing into functions
        tmp_dir = os.path.abspath(tmp_dir)
        out_dir = os.path.abspath(out_dir)

        st.subheader("Camera Settings ("+cam_name+")")
        cam0 = config["streams"][cam_name]
        params = cam0["camera"]["params"]

        trigger_type_options = ["hardware", "software"]
        current_trigger_type = params["trigger"].get("type", "software")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            new_trigger_type = st.selectbox(
                "Trigger Type", 
                trigger_type_options, 
                index=trigger_type_options.index(current_trigger_type),
                key="trigger_select"
            )
        with col2:
            frames_per_second = st.number_input(
                "Frames Per Second", 
                min_value=1, 
                max_value=60, 
                value=int(cam0.get("frames_per_second", 6)),
                key="fps_input"
            )
        with col3:
            gain_val = st.number_input(
                "Gain",
                min_value=0,
                max_value=50,
                value=int(params.get("gain", 0)),
                key="gain_input"
            )
        with col4:
            frames_per_file = st.number_input(
                "Frames Per File",
                min_value=1,
                max_value=10000,
                value=int(cam0.get("frames_per_file", 360)),
                key="fpf_input"
            )
        
        if st.button("Save Config", key="save_bbimg_config"):
            config["tmp_dir"] = tmp_dir
            config["out_dir"] = out_dir
            params["trigger"]["type"] = new_trigger_type
            cam0["frames_per_second"] = frames_per_second
            params["gain"] = gain_val
            cam0["frames_per_file"] = frames_per_file
            functions_acquisition.save_bbimg_config(config)
            st.success("Config saved!")

        st.subheader("Run Acquisition")
        os.makedirs(tmp_dir, exist_ok=True)
        os.makedirs(out_dir, exist_ok=True)
        functions_acquisition.run_acquisition(tmp_dir, out_dir, frames_per_file, frames_per_second)

    st.divider()

    ########################################################################################################
    #### "Pipeline on Existing Videos"
    ########################################################################################################
    st.subheader("Pipeline on Existing Videos")
    input_dir = st.text_input("Pipeline input directory", value=os.path.join(out_dir,cam_name))
    result_dir = st.text_input("Pipeline output directory", value="data/out")
    input_dir = os.path.abspath(input_dir)
    result_dir = os.path.abspath(result_dir)

    # ------------------------
    # 1) PIPELINE SETTINGS
    # ------------------------
    with st.expander("Pipeline Settings", expanded=False):
        st.write("Set parameters for detection and tracking:")
        
        # First row
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            tag_pixel_diameter = st.number_input("tag_pixel_diameter", min_value=1.0, max_value=999.0, value=45.0)
        with col2:
            cm_per_pixel = st.number_input("cm_per_pixel", min_value=0.0, max_value=1.0, value=(200 / 5312))
        with col3:
            recalc_str = st.selectbox("recalc", ["false", "true"], index=0)
        with col4:
            timestamp_format = st.selectbox("timestamp_format", ["basler", "rpi"], index=0)
        with col5:
            use_trajectories_str = st.selectbox("use_trajectories", ["false", "true"], index=1)
        with col6:
            save_filetype = st.selectbox("save_filetype", ["parquet", "csv"], index=0)

    # Convert the "false"/"true" strings to boolean
    recalc = (recalc_str == "true")
    use_trajectories = (use_trajectories_str == "true")

    # ------------------------
    # 2) VIDEO SETTINGS
    # ------------------------
    with st.expander("Video Settings", expanded=False):
        st.write("Parameters for video visualizing the results:")

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            create_video_str = st.selectbox("create_video", ["false", "true"], index=1)
        with col2:
            scale_factor = st.number_input("scale_factor", min_value=0.01, max_value=1.0, value=0.25)
        with col3:
            track_history = st.number_input("track_history", min_value=0, max_value=9999, value=0)
        with col4:
            r_tagged = st.number_input("r_tagged", min_value=1, max_value=50, value=20)
        with col5:
            save_png_str = st.selectbox("save_png", ["false", "true"], index=0)

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            show_untagged_str = st.selectbox("show_untagged", ["false", "true"], index=0)            
        with col2:
            r_untagged = st.number_input("r_untagged", min_value=1, max_value=50, value=5)    

    # Convert booleans
    create_video = (create_video_str == "true")
    save_png = (save_png_str == "true")
    show_untagged = (show_untagged_str == "true")

    # should eventually make this an option to specify the extension
    detection_ext = '' if timestamp_format=='rpi' else '-detections'  
    tracks_ext = "-tracks"
    
    # COMBINE ALL PARAMETERS
    pipeline_params = {
        # Pipeline settings
        "tag_pixel_diameter": tag_pixel_diameter,
        "cm_per_pixel": cm_per_pixel,
        "recalc": recalc,
        "timestamp_format": timestamp_format,
        "use_trajectories": use_trajectories,
        "save_filetype": save_filetype,
        # Video settings
        "create_video": create_video,
        "scale_factor": scale_factor,
        "track_history": track_history,
        "r_untagged": r_untagged,
        "r_tagged": r_tagged,
        "save_png": save_png,
        "show_untagged": show_untagged,
        "detection_ext": detection_ext,
        "tracks_ext": tracks_ext
    }

    # ------------------------
    # 3) SHOW AVAILABLE VIDEOS
    # ------------------------

    # Button to refresh/collect available videos
    if st.button("Refresh Videos", key="refresh_btn"):
        # Gather multiple formats
        video_extensions = ["mp4", "avi", "h264"]
        vids = []
        for ext in video_extensions:
            vids.extend(
                glob.glob(os.path.join(input_dir, f"*.{ext}"))
            )
        # Filter out "tracked-video" or any custom exclusion
        videos = sorted([v for v in vids if "tracked-video" not in os.path.basename(v)])
        st.session_state["videos"] = videos

    # Retrieve from session state
    videos = st.session_state.get("videos", [])

    if not videos:
        st.info("No videos found. Click 'Refresh Videos'.")
        return
    
    st.write("### Available Videos")
    
    # Checkbox for "Select All"
    select_all = st.checkbox("Select All", key="select_all_checkbox")

    # -------------------------------------------------------------------------
    # 2) Build a DataFrame with info for each video
    # -------------------------------------------------------------------------
    table_data = []
    for raw_video_path in videos:
        base = os.path.basename(raw_video_path)

        # Check if we have detections, tracks, or a tracked video
        detections_exist, tracks_exist, output_video_exists = video_has_results(
            raw_video_path, 
            save_filetype, 
            result_dir,
            detection_ext=detection_ext
        )

        # If a tracked video exists, use it as the path to play. Otherwise use raw video.
        base_stem = os.path.splitext(base)[0]

        table_data.append({
            "select": select_all,
            "video_name": base,
            "has_detections": detections_exist,
            "has_tracks": tracks_exist,
            "has_video": output_video_exists
        })

    df_table = pd.DataFrame(table_data)

    # -------------------------------------------------------------------------
    # 3) Render with st.data_editor
    # -------------------------------------------------------------------------
    edited_df = st.data_editor(
        df_table,
        column_config={
            "select": st.column_config.CheckboxColumn(
                "Select",
                help="Check to process or play this video",
                width="small",
            ),
            "video_name": "Video name",
            "has_detections": st.column_config.CheckboxColumn(
                "Detections?",
                disabled=True
            ),
            "has_tracks": st.column_config.CheckboxColumn(
                "Tracks?",
                disabled=True
            ),
            "has_video": st.column_config.CheckboxColumn(
                "Video File?",
                disabled=True
            )
        },
        hide_index=True,
        key="videos_table",
    )

    # -------------------------------------------------------------------------
    # 4) Gather selected rows
    # -------------------------------------------------------------------------
    selected_rows = edited_df[edited_df["select"] == True]
    st.write(f"**Selected rows:** {len(selected_rows)}")

    # Button to run pipeline
    if st.button("Run Pipeline on Selected"):
        if selected_rows.empty:
            st.warning("No videos selected.")
        else:
            # Here you would pass the selected videos to your pipeline
            for _, row in selected_rows.iterrows():
                video_name = row["video_name"]
                video_full_path = os.path.join(input_dir, video_name)
                functions_data_and_pipeline.run_pipeline_on_video(video_full_path, result_dir, **pipeline_params)
                st.write(f"Running pipeline on: {video_name}")
            st.success("Pipeline completed on selected files.")

    # -------------------------------------------------------------------------
    # 5) "Play Selected" button
    # -------------------------------------------------------------------------
    selected_rows = edited_df[edited_df["select"] == True]
    if st.button("Play Selected"):
        if selected_rows.empty:
            st.warning("No rows selected!")
        else:
            for _, row in selected_rows.iterrows():
                if row['has_video']:
                    st.write(f"Tracked video for {row['video_name']}")
                    base_name = os.path.splitext(os.path.basename(row['video_name']))[0]
                    video_path_to_play = os.path.join(result_dir, f"{base_name}-tracked-video.mp4")
                else:
                    st.write(f"Raw video for {row['video_name']}")
                    video_path_to_play = os.path.join(input_dir, f"{row['video_name']}")

                st.video(video_path_to_play)
                st.divider()


if __name__ == "__main__":
    main()