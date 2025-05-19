# ComfyUI Workflow Tester

A testing utility for comparing different ComfyUI workflows across multiple inputs. The tool supports processing both images and videos through multiple workflows and generates visual comparisons of the results.

Currently supports workflows that take a single image as input.

## Features

- Support for both image and video inputs
- Generate comparison grids for image results
- Create HTML tables for easy result visualization
- Support for video frame extraction and reconstruction
- Automatic output organization with timestamped directories
- Configurable settings via YAML
- Intelligent FPS adjustment for video processing
- Support for Base64 image loading for faster workflow execution

## Directory Structure

```
workflow-tester-comfyui/
├── workflows/          # Place your ComfyUI workflow files here
├── input_images/       # Place your input images and videos here
├── output_images/      # Generated outputs (auto-created)
│   └── YYYYMMDD_HHMMSS/  # Timestamped output directories
├── workflow_test.py    # Main testing script
├── config.yaml         # Configuration file
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Installation

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

The `config.yaml` file allows you to customize various aspects of the testing process:

- Server settings (URL, timeout)
- Directory paths
- Video processing parameters (max frames, FPS)
- Image processing settings
- Workflow matching patterns
- Output formatting options

### Video Processing Configuration

You can use the --video-only argument to only process videos in the input folder, and skip the report generation. 

The video processing section in `config.yaml` allows fine control over how videos are processed:

```yaml
video:
  max_frames: 100  # Maximum number of frames to process from each video
  fps: 30  # Fallback FPS if original can't be determined
  temp_dir: "temp_frames"  # Directory for temporary frame storage
  select_every_n: 2  # Process every Nth frame (1 = all frames, 2 = every other frame, etc.)
  skip_first_frames: 0  # Number of frames to skip at the start of the video
```

Key settings to understand:

- **select_every_n**: Controls how many frames are sampled for processing
  - Set to `1` to process every frame (slowest, highest quality)
  - Set to `2` to process every other frame (half the processing time)
  - Higher values skip more frames, making processing faster but potentially reducing quality
  
- **FPS Handling**: The tool automatically adjusts the output video's FPS based on the `select_every_n` setting:
  - If processing every frame (`select_every_n: 1`), the original video's FPS is maintained
  - If processing every Nth frame, the FPS is divided by N to maintain correct playback speed
  - Example: If source video is 30 FPS and `select_every_n: 3`, output video will be 10 FPS
  
- **max_frames**: Limits the total number of frames processed from each video
  - Useful for testing with longer videos without processing the entire file

## Workflow Types Support

### Base64 Image Loading (Fast Method)

The tool now automatically detects workflows that use `LoadImageB64` or `LoadImageBase64` nodes, and will:

1. Convert input images directly to base64-encoded strings
2. Include the encoded image data directly in the workflow JSON
3. Send the workflow to ComfyUI without separate image upload steps

This method can be faster when executing this over network. 

The base64 image loader can be found in https://github.com/ryanontheinside/ComfyUI_RealtimeNodes 

To take advantage of this optimization:
- Replace standard `LoadImage` nodes with `LoadImageB64` nodes in your workflows
- The tool will automatically detect these nodes and use the faster method
- The standard image upload method will still be used as a fallback for workflows with regular `LoadImage` nodes

## Usage

1. Configure your settings in `config.yaml`
2. Place your ComfyUI workflow files in the `workflows` directory
3. Place your test images/videos in the `input_images` directory
4. Run the test script:
```bash
python workflow_test.py --config config.yaml
```

### Command Line Options

The script supports several command line options:

```bash
# Process both images and videos (default behavior)
python workflow_test.py --config config.yaml

# Only process videos, skipping image processing and report generation
python workflow_test.py --config config.yaml --video-only

# Only generate HTML report from existing output directory
python workflow_test.py --config config.yaml --html-only --output-dir path/to/output
```

- `--config`: Specify the configuration file path
- `--video-only`: Process only video files, skip image processing and report generation
- `--html-only`: Only generate an HTML report from an existing output directory
- `--output-dir`: Specify output directory for HTML-only mode

### Supported File Types

- Images: Any format supported by PIL (png, jpg, jpeg, etc.)
- Videos: mp4, avi, mov, mkv, webm

## Output

The script creates a new timestamped directory for each test run under `output_images/`. For each run, you'll get:

- Processed images/videos named according to the workflow used
- A comparison grid showing all image results side by side
- An HTML table for interactive result viewing
- Progress information in the console

## Notes

- Video processing may take longer depending on the length and number of frames
- Make sure you have sufficient disk space for temporary frame storage
- The comparison grid and HTML table are generated only for image inputs
- Video outputs are saved individually in the output directory
- Currently only supports workflows that take a single image as input
- To adapt for different workflow systems, modify the workflow loading and processing functions 

# Example
![Image](https://github.com/user-attachments/assets/3bce229a-0abc-4b4c-b237-da9cab41c6eb)