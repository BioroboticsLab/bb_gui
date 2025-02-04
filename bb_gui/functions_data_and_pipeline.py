import streamlit as st
import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

import bb_behavior.io.videos
import bb_behavior.tracking
from bb_binary.parsing import parse_video_fname
from bb_behavior.vis.create_tracking_video import create_tracking_video
from datetime import datetime
import pytz
import cv2

########################################################
# detection/tracking/pipeline code
########################################################

def get_video_fps(video_path):
    """Extracts FPS from video metadata using OpenCV."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)  # Read FPS property
    cap.release()

    if fps > 0:
        return int(fps)  # Ensure it's an integer
    else:
        return None  # Return None if FPS extraction fails

def get_detections(video_path, tag_pixel_diameter, use_clahe=True):
    # check for timestamps file
    if os.path.isfile(video_path[:-4] + ".txt"):
        frame_info, video_dataframe = bb_behavior.tracking.detect_markers_in_beesbook_video(
            video_path,
            ts_format="basler",
            tag_pixel_diameter=tag_pixel_diameter,
            verbose=False,
            decoder_pipeline=None,
            n_frames=None,
            cam_id=0,
            confidence_filter=0.001,
            clahe=use_clahe,
            use_parallel_jobs=True,
            progress=None,
        )
    else:
        fps = get_video_fps(video_path)
        frame_info, video_dataframe = bb_behavior.tracking.detect_markers_in_video(
            video_path,
            tag_pixel_diameter=tag_pixel_diameter,
            fps=fps,
            verbose=False,
            decoder_pipeline=None,
            n_frames=None,
            cam_id=0,
            confidence_filter=0.001,
            clahe=use_clahe,
            use_parallel_jobs=True,
            progress=None,
        )
    if video_dataframe is None:  # return an empty dataframe
        video_dataframe = pd.DataFrame(columns=['localizerSaliency', 'beeID', 'xpos', 'ypos', 'camID', 'zrotation',
       'timestamp', 'frameIdx', 'frameId', 'detection_index', 'detection_type',
       'confidence'])
    return frame_info, video_dataframe

def get_tracks(video_dataframe,cm_per_pixel):
    # Select only tagged animals for tracking
    video_dataframe = video_dataframe.copy()
    video_dataframe = video_dataframe[video_dataframe.detection_type == "TaggedBee"]    
    # get the model paths, which were downloaded during install (from bb_pipeline_models)
    model_dir = os.getenv('CONDA_PREFIX') + '/pipeline_models'
    detection_model_path = os.path.join(model_dir, 'detection_model_4.json')
    tracklet_model_path = os.path.join(model_dir,'tracklet_model_8.json')
    
    tracks_df = bb_behavior.tracking.track_detections_dataframe(
            video_dataframe,
            homography_scale=cm_per_pixel, 
            cam_id=0, 
            tracker_settings_kwargs=dict(detection_model_path=detection_model_path,
                                         tracklet_model_path=tracklet_model_path))    
    if tracks_df is None:  # return an empty dataframe 
        tracks_df = pd.DataFrame(columns=['bee_id', 'bee_id_confidence', 'track_id', 'x_pixels', 'y_pixels',
       'orientation_pixels', 'x_hive', 'y_hive', 'orientation_hive',
       'timestamp_posix', 'timestamp', 'frame_id', 'detection_type',
       'detection_index', 'detection_confidence'])
    tracks_df['detection_type'] = 'TaggedBee'  # save this as a string
    return tracks_df

def display_detection_results(first_frame_image,video_dataframe,detectionspng_filename):
    f, ax = plt.subplots(figsize=(15, 15))
    ax.imshow(first_frame_image)
    if (video_dataframe is not None)&(len(video_dataframe)>0):  # handle also some special cases where detections failed
        x_pixels = video_dataframe['xpos'].values
        y_pixels = video_dataframe['ypos'].values 
        orientations = video_dataframe['zrotation'].values  
        # Plot detections
        plt.scatter(x_pixels, y_pixels, s=10, c='red', marker='o',alpha=0.3)
        # Plot orientation arrows
        for x, y, ori in zip(x_pixels, y_pixels, orientations):
            dx = 40 * np.cos(ori)  # Adjust the length as needed
            dy = 40 * np.sin(ori)
            plt.arrow(x, y, dx, dy, color='yellow', head_width=15, head_length=15)
    plt.savefig(detectionspng_filename,bbox_inches="tight")
    plt.close()
    return True

def run_pipeline_on_video(video_path, resultdir, tag_pixel_diameter=38, cm_per_pixel=1, scale_factor=0.25, recalc=False, 
                          timestamp_format='basler', save_png=False, use_trajectories=True, save_filetype="parquet",
                          create_video=False, use_clahe=True,
                          track_history=0, r_tagged=20, r_untagged=5, show_untagged=False, 
                          detection_ext='-detections', tracks_ext='-tracks'):
    """Runs detection/tracking pipeline on a single video."""

    st.write(f"Running pipeline on: {video_path}")
    base_name = ".".join(os.path.basename(video_path).split(".")[:-1])
    detections_filename = os.path.join(resultdir, f"{base_name}{detection_ext}.{save_filetype}")
    detectionspng_filename = os.path.join(resultdir, base_name + f"-detections.png")
    tracks_filename = os.path.join(resultdir, f"{base_name}{tracks_ext}.{save_filetype}")    
    output_video_filename = os.path.join(resultdir, base_name + "-tracked-video.mp4")

    # 1) Load or compute detections
    if os.path.isfile(detections_filename) and not recalc:
        st.write(f"Loading existing detections from {detections_filename}")
        if save_filetype == "csv":
            video_dataframe = pd.read_csv(detections_filename)
        else:
            video_dataframe = pd.read_parquet(detections_filename)
    else:
        st.write("Running detection pipeline...")
        frame_info, video_dataframe = get_detections(video_path, tag_pixel_diameter, use_clahe=use_clahe)
        if save_filetype == "csv":
            video_dataframe.to_csv(detections_filename, index=False)
        else:
            video_dataframe.to_parquet(detections_filename)

    if save_png:
        first_frame_image = bb_behavior.io.videos.get_first_frame_from_video(video_path)
        display_detection_results(first_frame_image, video_dataframe, detectionspng_filename)

    # 3) Tracking
    if use_trajectories:
        if os.path.isfile(tracks_filename) and not recalc:
            st.write(f"Loading existing tracks from {tracks_filename}")
            if save_filetype == "csv":
                tracks_df = pd.read_csv(tracks_filename)
            else:
                tracks_df = pd.read_parquet(tracks_filename)
        else:
            st.write("Computing new tracks...")
            tracks_df = get_tracks(video_dataframe, cm_per_pixel)
            if save_filetype == "csv":
                tracks_df.to_csv(tracks_filename, index=False)
            else:
                tracks_df.to_parquet(tracks_filename)
    else:
        tracks_df = None

    # 4) parse video start

    ## create video with tracking result
    if timestamp_format in ['beesbook', 'iso', 'bbb', 'basler']:
        _, video_start_timestamp, _ = parse_video_fname(video_path,format=timestamp_format)
    elif timestamp_format=='rpi':
        timestamp_str = os.path.basename(video_path).split('_')[-1].replace('.h264', '')
        video_start_timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d-%H-%M-%S')
        video_start_timestamp = pd.Timestamp(video_start_timestamp).tz_localize(pytz.timezone('Europe/Berlin')).tz_convert(pytz.UTC)

    # 5) create tracked video
    # only include detections dataframe if it is valid to prevent errors
    video_dataframe_input = None
    if video_dataframe is not None:
        if show_untagged & (len(video_dataframe)>0):
            video_dataframe_input = video_dataframe
    # same for tracks df
    tracks_df_input = None
    if tracks_df is not None:
        if use_trajectories & (len(tracks_df)>0):
            tracks_df_input = tracks_df
    if create_video:
        st.write("Creating tracked video...")
        create_tracking_video(
            video_path,
            output_video_filename,
            video_start_timestamp,
            tracks_df=tracks_df_input,
            track_history=track_history,
            video_dataframe=video_dataframe_input,
            scale_factor=scale_factor,
            r_tagged=r_tagged,
            r_untagged=r_untagged
        )
        st.success(f"Pipeline and video complete! Output: {output_video_filename}")
    else:
        st.success(f"Pipeline complete!")