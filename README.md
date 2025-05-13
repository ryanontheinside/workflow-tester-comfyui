# ComfyUI Workflow Tester

A testing utility for comparing different ComfyUI workflows across multiple inputs. The tool supports processing both images and videos through multiple workflows and generates visual comparisons of the results.

Currently supports:
- One single "Load Image" input node,
- Two "Load Image" input nodes with the titles "Load Image" and "Load Image (Prev)" (for video only).

## Features

- Support for both image and video inputs ("Load Image" as title)
- Support for previous frame as optional input ("Load Image (Prev)" as title)
- Generate comparison grids for image results
- Create HTML tables for easy result visualization
- Support for video frame extraction and reconstruction
- Automatic output organization with timestamped directories
- Configurable settings via YAML

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

## Usage

1. Configure your settings in `config.yaml`
2. Place your ComfyUI workflow files in the `workflows` directory
3. Place your test images/videos in the `input_images` directory
4. Run the test script:
```bash
python workflow_test.py
```

You can also specify a different config file:
```bash
python workflow_test.py --config custom_config.yaml
```

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
- To use the previous frame feature, set a secondary LoadImage node with the title `Load Image (Prev)`. The previous input frame will be appended to that node.

# Example
![Image](https://github.com/user-attachments/assets/3bce229a-0abc-4b4c-b237-da9cab41c6eb)