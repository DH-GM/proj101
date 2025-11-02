#!/usr/bin/env python3
"""
Video to ASCII Converter
Extracts frames from video and converts each to ASCII art
"""
import cv2
import subprocess
import sys
from pathlib import Path
from PIL import Image


def video_to_ascii_frames(video_path: str, output_dir: str = "ascii_frames", 
                          fps: int = 1, max_width: int = 80, max_seconds: int = None):
    """
    Convert video to ASCII frames.
    
    Args:
        video_path: Path to input video file
        output_dir: Directory to save ASCII frames
        fps: Frames per second to extract (1 = 1 frame/second)
        max_width: Maximum width in characters for ASCII output
        max_seconds: Maximum seconds to process (None = entire video)
    """
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Open video
    video = cv2.VideoCapture(video_path)
    video_fps = video.get(cv2.CAP_PROP_FPS)
    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / video_fps
    
    print(f"📹 Video info:")
    print(f"   FPS: {video_fps}")
    print(f"   Total frames: {total_frames}")
    print(f"   Duration: {duration:.2f}s")
    print(f"   Extracting {fps} frame(s) per second")
    
    # Calculate frame interval
    frame_interval = int(video_fps / fps)
    
    frame_count = 0
    saved_count = 0
    max_frames_to_save = int(max_seconds * fps) if max_seconds else None
    
    while True:
        ret, frame = video.read()
        if not ret:
            break
        
        # Stop if we've saved enough frames
        if max_frames_to_save and saved_count >= max_frames_to_save:
            print(f"⏱️  Reached {max_seconds}s limit ({saved_count} frames), stopping...")
            break
        
        # Extract frames at specified interval
        if frame_count % frame_interval == 0:
            # Resize frame to fit screen (smaller = faster processing)
            height, width = frame.shape[:2]
            new_width = 400  # Small size for faster processing
            new_height = int(height * (new_width / width))
            resized_frame = cv2.resize(frame, (new_width, new_height))
            
            temp_frame = output_path / f"temp_frame_{saved_count}.png"
            cv2.imwrite(str(temp_frame), resized_frame)
            
            # Convert to ASCII TEXT (terminal-friendly)
            ascii_output = output_path / f"frame_{saved_count:04d}.txt"
            
            # Run asciifer via poetry (handles dependencies)
            try:
                font_path = "/System/Library/Fonts/Monaco.ttf"
                
                # Use absolute paths since we're running from asciifer directory
                temp_frame_abs = temp_frame.absolute()
                ascii_output_abs = ascii_output.absolute()
                
                result = subprocess.run([
                    "poetry",
                    "run",
                    "python",
                    "asciifer.py",
                    "--output-text", str(ascii_output_abs),  
                    "--font", font_path,
                    "--font-size", "8",  # Smaller font for more detail
                    str(temp_frame_abs)
                ], cwd="asciifer", check=True, capture_output=True, text=True)
                
                print(f"✅ Frame {saved_count}/{int(duration * fps)} converted")
                saved_count += 1
                
                # Clean up temp frame
                temp_frame.unlink()
                
            except subprocess.CalledProcessError as e:
                print(f"❌ Error converting frame {saved_count}:")
                print(f"   Return code: {e.returncode}")
                print(f"   Stderr: {e.stderr}")
                print(f"   Stdout: {e.stdout}")
                # Don't stop, try next frame
                if temp_frame.exists():
                    temp_frame.unlink()
        
        frame_count += 1
    
    video.release()
    
    # Save metadata
    metadata = output_path / "metadata.txt"
    metadata.write_text(f"total_frames={saved_count}\nfps={fps}\n")
    
    print(f"\n✨ Done! Converted {saved_count} frames to {output_path}/")
    return saved_count


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Convert video to ASCII frames")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--output", "-o", default="ascii_frames", help="Output directory")
    parser.add_argument("--fps", type=int, default=1, help="Frames per second to extract")
    parser.add_argument("--width", type=int, default=80, help="Max ASCII width")
    
    args = parser.parse_args()
    
    video_to_ascii_frames(args.video, args.output, args.fps, args.width)

