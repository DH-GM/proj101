#!/usr/bin/env python3
"""
Convert the subway.mp4 video to ASCII frames
Run this script to generate ASCII frames for the video
"""
from video_to_ascii import video_to_ascii_frames

# Convert subway video
video_path = "/Users/nursultansagyntay/Documents/subway.mp4"
output_dir = "subway_ascii_frames"

print("🚇 Converting subway.mp4 to ASCII frames...")
print("This may take a few minutes...\n")

# Extract 2 frames per second for first 10 seconds (40 total frames)
frame_count = video_to_ascii_frames(
    video_path=video_path,
    output_dir=output_dir,
    fps=4,  # 2 frames per second (half bitrate)
    max_width=80,
    max_seconds=10  # Only process first 10 seconds
)

print(f"\n✨ Success! Generated {frame_count} ASCII frames")
print(f"📁 Saved to: {output_dir}/")
print(f"\nTo use in the TUI, import ASCIIVideoPlayer:")
print(f'  from ascii_video_widget import ASCIIVideoPlayer')
print(f'  yield ASCIIVideoPlayer("{output_dir}", fps=2)')

