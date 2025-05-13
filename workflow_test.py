import json
import urllib.request
import time
import io
import os
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import glob
import cv2
import numpy as np
import tempfile
from tqdm import tqdm
import yaml
import argparse
import sys
import shutil

def load_config(config_path):
    """Load configuration from YAML file."""
    if not os.path.exists(config_path):
        print(f"Error: Config file '{config_path}' not found")
        sys.exit(1)
        
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Validate required config sections
    required_sections = ['server', 'directories', 'video', 'image', 'workflow', 'output']
    for section in required_sections:
        if section not in config:
            print(f"Error: Missing required section '{section}' in config file")
            sys.exit(1)
    
    return config

def create_output_directory(config):
    """Create timestamped output directory with subfolders."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(config['directories']['output_images'], timestamp)
    
    # Create main output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Create subdirectories
    os.makedirs(os.path.join(output_dir, config['directories']['output_subfolders']['images']), exist_ok=True)
    os.makedirs(os.path.join(output_dir, config['directories']['output_subfolders']['videos']), exist_ok=True)
    os.makedirs(os.path.join(output_dir, config['directories']['output_subfolders']['inputs']), exist_ok=True)
    os.makedirs(os.path.join(output_dir, config['directories']['output_subfolders']['workflows']), exist_ok=True)
    
    # Copy CSS file to output directory
    css_source = os.path.join(os.path.dirname(__file__), 'report.css')
    if os.path.exists(css_source):
        shutil.copy2(css_source, output_dir)
    
    return output_dir, timestamp

def copy_input_images(input_images, output_dir, config):
    """Copy input images to the inputs subdirectory."""
    input_copies = []
    for input_img in input_images:
        # Copy the input image to the inputs subdirectory
        input_filename = os.path.basename(input_img)
        input_copy_path = os.path.join(output_dir, config['directories']['output_subfolders']['inputs'], input_filename)
        shutil.copy2(input_img, input_copy_path)
        input_copies.append(input_copy_path)
    return input_copies

def copy_workflow_files(workflow_files, output_dir, config):
    """Copy workflow files to the workflows subdirectory."""
    workflow_copies = []
    for workflow_file in workflow_files:
        # Copy the workflow file to the workflows subdirectory
        workflow_filename = os.path.basename(workflow_file)
        workflow_copy_path = os.path.join(output_dir, config['directories']['output_subfolders']['workflows'], workflow_filename)
        shutil.copy2(workflow_file, workflow_copy_path)
        workflow_copies.append(workflow_copy_path)
    return workflow_copies

def create_comparison_grid(output_dir, image_paths, workflow_names, input_images, config, timestamp):
    # Calculate grid dimensions
    num_workflows = len(workflow_names)
    num_input_images = len(input_images)
    
    # Get dimensions from first image
    with Image.open(image_paths[0]) as img:
        width, height = img.size
    
    # Add padding for labels
    label_height = config['output']['label_height']
    label_width = config['output']['label_width']
    padding = config['output']['grid_padding']
    
    # Create a new image for the grid with space for labels
    total_width = width * (num_workflows + 1) + label_width + padding
    total_height = height * num_input_images + label_height + padding
    grid = Image.new('RGB', (total_width, total_height), 'white')
    
    # Create a drawing context
    draw = ImageDraw.Draw(grid)
    
    # Try to load a font, fall back to default if not available
    try:
        font = ImageFont.truetype("arial.ttf", config['output']['font_size'])
    except:
        font = ImageFont.load_default()
    
    # Draw column labels (workflow names)
    draw.text((label_width + padding + width//2, padding), "Input Image", fill='black', font=font, anchor="mm")
    for col_idx, name in enumerate(workflow_names):
        x = label_width + padding + (col_idx + 1) * width + width//2
        y = padding
        display_name = name.replace('.json', '')
        draw.text((x, y), display_name, fill='black', font=font, anchor="mm")
    
    # Draw row labels (input image names)
    for row_idx, img_path in enumerate(input_images):
        x = padding
        y = label_height + row_idx * height + height//2
        name = os.path.splitext(os.path.basename(img_path))[0]
        draw.text((x, y), name, fill='black', font=font, anchor="lm")
    
    # Create a mapping of filenames to their positions in the grid
    image_map = {}
    for path in image_paths:
        filename = os.path.basename(path)
        workflow_name = None
        input_name = None
        
        for wf_name in workflow_names:
            wf_base = wf_name.replace('.json', '')
            if filename.startswith(wf_base + '_'):
                workflow_name = wf_name
                input_name = filename[len(wf_base) + 1:].rsplit('.', 1)[0]
                break
        
        if workflow_name and input_name:
            image_map[(workflow_name, input_name)] = path
    
    # Place images in grid
    for row_idx, input_img in enumerate(input_images):
        try:
            with Image.open(input_img) as img:
                x = label_width + padding
                y = label_height + row_idx * height
                grid.paste(img, (x, y))
        except Exception as e:
            print(f"Error loading input image {input_img}: {e}")
        
        input_name = os.path.splitext(os.path.basename(input_img))[0]
        for col_idx, workflow_name in enumerate(workflow_names):
            key = (workflow_name, input_name)
            if key in image_map:
                try:
                    with Image.open(image_map[key]) as img:
                        x = label_width + padding + (col_idx + 1) * width
                        y = label_height + row_idx * height
                        grid.paste(img, (x, y))
                except Exception as e:
                    print(f"Error loading image {image_map[key]}: {e}")
    
    # Save the grid with timestamp
    grid_path = os.path.join(output_dir, f"comparison_grid_{timestamp}.png")
    grid.save(grid_path, quality=config['image']['quality'])
    
    return grid_path

def create_html_table(output_dir, image_paths, workflow_names, input_images, video_paths, workflow_files, config, timestamp):
    # Create a mapping of filenames to their paths
    image_map = {}
    for path in image_paths:
        filename = os.path.basename(path)
        workflow_name = None
        input_name = None
        
        for wf_name in workflow_names:
            wf_base = wf_name.replace('.json', '')
            if filename.startswith(wf_base + '_'):
                workflow_name = wf_name
                input_name = filename[len(wf_base) + 1:].rsplit('.', 1)[0]
                break
        
        if workflow_name and input_name:
            image_map[(workflow_name, input_name)] = path

    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="report.css">
    </head>
    <body>
        <h1>Workflow Comparison Results</h1>
        <p>Generated on: %s</p>
        
        <h2 class="section-title">Workflows</h2>
        <ul>
    """ % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    # Add workflow links
    for workflow_file in workflow_files:
        workflow_name = os.path.basename(workflow_file)
        rel_path = f"{config['directories']['output_subfolders']['workflows']}/{workflow_name}"
        display_name = workflow_name.replace('.json', '')
        html_content += f'<li><a href="{rel_path}" class="workflow-link" target="_blank">{display_name}</a></li>\n'
    
    html_content += """
        </ul>
        
        <h2 class="section-title">Image Results</h2>
        <table>
            <tr>
                <th>Input Image</th>
                <th>Original</th>
    """
    
    # Add workflow names as column headers
    for name in workflow_names:
        display_name = name.replace('.json', '')
        rel_path = f"{config['directories']['output_subfolders']['workflows']}/{name}"
        html_content += f'<th class="workflow-name"><a href="{rel_path}" class="workflow-link" target="_blank">{display_name}</a></th>\n'
    
    html_content += "</tr>\n"
    
    # Add rows for each input image
    for input_img in input_images:
        input_name = os.path.splitext(os.path.basename(input_img))[0]
        html_content += "<tr>\n"
        html_content += f'<td class="image-name">{input_name}</td>\n'
        
        # Add the input image
        input_filename = os.path.basename(input_img)
        rel_input_path = f"{config['directories']['output_subfolders']['inputs']}/{input_filename}"
        html_content += f'<td><img src="{rel_input_path}" alt="Input"></td>\n'
        
        # Add cells for each workflow
        for workflow_name in workflow_names:
            key = (workflow_name, input_name)
            if key in image_map:
                filename = os.path.basename(image_map[key])
                rel_path = f"{config['directories']['output_subfolders']['images']}/{filename}"
                html_content += f'<td><img src="{rel_path}" alt="Result"></td>\n'
            else:
                html_content += '<td>No image available</td>\n'
        
        html_content += "</tr>\n"
    
    html_content += """
        </table>
    """
    
    # Add video section if there are any videos in the video directory
    video_dir = os.path.join(output_dir, config['directories']['output_subfolders']['videos'])
    if os.path.exists(video_dir) and len(os.listdir(video_dir)) > 0:
        html_content += """
        <h2 class="section-title">Video Results</h2>
        <table>
            <tr>
                <th>INPUT VIDEO</th>
                <th>ORIGINAL</th>
        """
        
        # Add workflow names as column headers
        for name in workflow_names:
            display_name = name.replace('.json', '')
            rel_path = f"{config['directories']['output_subfolders']['workflows']}/{name}"
            html_content += f'<th class="workflow-name"><a href="{rel_path}" class="workflow-link" target="_blank">{display_name}</a></th>\n'
        
        html_content += "</tr>\n"
        
        # Find all input video files
        inputs_dir = os.path.join(output_dir, config['directories']['output_subfolders']['inputs'])
        input_video_files = [f for f in glob.glob(os.path.join(inputs_dir, "*.*")) if is_video_file(f)]
        
        # Create a map of processed videos by workflow and input name
        processed_videos = {}
        for video_path in glob.glob(os.path.join(video_dir, "*.mp4")):
            filename = os.path.basename(video_path)
            
            # Extract workflow name and input name from filename pattern: workflow_inputname.mp4
            for wf_name in workflow_names:
                wf_base = wf_name.replace('.json', '')
                if filename.startswith(wf_base + '_'):
                    input_name = filename[len(wf_base) + 1:].rsplit('.', 1)[0]
                    if (wf_name, input_name) not in processed_videos:
                        processed_videos[(wf_name, input_name)] = video_path
        
        # Add rows for each input video
        for input_video in input_video_files:
            input_name = os.path.splitext(os.path.basename(input_video))[0]
            html_content += "<tr>\n"
            html_content += f'<td class="image-name">{input_name}</td>\n'
            
            # Add the input video
            input_filename = os.path.basename(input_video)
            rel_input_path = f"{config['directories']['output_subfolders']['inputs']}/{input_filename}"
            
            # Handle different video extensions
            video_ext = os.path.splitext(input_filename)[1].lower()
            mime_type = "video/mp4" if video_ext == ".mp4" else "video/quicktime" if video_ext == ".mov" else "video/mp4"
            
            html_content += f'<td><video controls preload="metadata" width="100%"><source src="{rel_input_path}" type="{mime_type}">Your browser does not support the video tag.</video></td>\n'
            
            # Add cells for each workflow
            for workflow_name in workflow_names:
                key = (workflow_name, input_name)
                
                if key in processed_videos:
                    filename = os.path.basename(processed_videos[key])
                    rel_path = f"{config['directories']['output_subfolders']['videos']}/{filename}"
                    html_content += f'<td><video controls preload="metadata" width="100%"><source src="{rel_path}" type="video/mp4">Your browser does not support the video tag.</video></td>\n'
                else:
                    html_content += '<td>No video available</td>\n'
            
            html_content += "</tr>\n"
        
        html_content += """
        </table>
        """
    
    html_content += """
    </body>
    </html>
    """
    
    # Save the HTML file with timestamp
    html_path = os.path.join(output_dir, f"comparison_table_{timestamp}.html")
    with open(html_path, "w") as f:
        f.write(html_content)
    
    return html_path

def create_zip_archive(output_dir, timestamp):
    """Create a zip archive of the output directory."""
    # Create zip in parent directory first
    parent_dir = os.path.dirname(output_dir)
    temp_zip_path = os.path.join(parent_dir, f"temp_results_{timestamp}.zip")
    shutil.make_archive(temp_zip_path[:-4], 'zip', output_dir)
    
    # Move to final location
    final_zip_path = os.path.join(output_dir, f"results_{timestamp}.zip")
    shutil.move(temp_zip_path, final_zip_path)
    
    return final_zip_path

def upload_image(image_path, filename, config, overwrite=False):
    # Read the image file
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    # Create a simple multipart form request
    boundary = '----WebKitFormBoundary'
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}'
    }
    
    # Create the multipart form data
    data = []
    data.append(f'--{boundary}'.encode())
    data.append(f'Content-Disposition: form-data; name="image"; filename="{filename}"'.encode())
    data.append(b'Content-Type: image/png')
    data.append(b'')
    data.append(image_data)
    data.append(f'--{boundary}'.encode())
    data.append(b'Content-Disposition: form-data; name="overwrite"')
    data.append(b'')
    data.append(str(overwrite).lower().encode())
    data.append(f'--{boundary}--'.encode())
    
    # Join the data with newlines
    body = b'\r\n'.join(data)
    
    # Create and send the request
    req = urllib.request.Request(
        f"{config['server']['url']}/upload/image",
        data=body,
        headers=headers,
        method='POST'
    )
    
    try:
        response = urllib.request.urlopen(req, timeout=config['server']['timeout'])
        return json.loads(response.read())
    except urllib.error.HTTPError as e:
        print(f"Error uploading image: {e}")
        print(f"Response: {e.read().decode()}")
        raise

def queue_prompt(prompt, config):
    p = {"prompt": prompt}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"{config['server']['url']}/prompt", data=data)
    response = urllib.request.urlopen(req, timeout=config['server']['timeout'])
    return json.loads(response.read())

def get_image(filename, subfolder, folder_type, config):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"{config['server']['url']}/view?{url_values}", timeout=config['server']['timeout']) as response:
        return response.read()

def get_history(prompt_id, config):
    with urllib.request.urlopen(f"{config['server']['url']}/history/{prompt_id}", timeout=config['server']['timeout']) as response:
        return json.loads(response.read())

def get_images(prompt, config):
    # Queue the prompt
    prompt_id = queue_prompt(prompt, config)['prompt_id']
    print(f"Prompt queued with ID: {prompt_id}")
    
    # Wait for the execution to complete
    while True:
        history = get_history(prompt_id, config)
        if prompt_id in history:
            break
        time.sleep(0.1)
    
    # Get the output images
    output_images = {}
    history = history[prompt_id]
    
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        if 'images' in node_output:
            images_output = []
            for image in node_output['images']:
                image_data = get_image(image['filename'], image['subfolder'], image['type'], config)
                images_output.append(image_data)
            output_images[node_id] = images_output
    
    return output_images

def load_workflow(filename, config):
    workflow_path = os.path.join(config['directories']['workflows'], filename)
    with open(workflow_path, 'r') as f:
        return json.load(f)

def update_workflow_with_image(workflow, image_name, prev_frame_name):
    # Update both current frame and previous frame LoadImage nodes
    for node_id, node_data in workflow.items():
        if node_data.get('class_type') == 'LoadImage':
            # Check the node's title to determine which image to update
            title = node_data.get('_meta', {}).get('title', '')
            if title == 'Load Image':
                # Update current frame
                node_data['inputs'] = {
                    "image": image_name,
                    "upload": "true"
                }
            elif title == 'Load Image (Prev)' and prev_frame_name:
                # Update previous frame if provided
                node_data['inputs'] = {
                    "image": prev_frame_name,
                    "upload": "true"
                }
    return workflow

def process_workflow(workflow_file, image_path, prev_frame_path, output_dir, config):
    print(f"\nProcessing workflow: {workflow_file}")
    print(f"Using image: {image_path}")
    print(f"Using previous frame: {prev_frame_path}")
    
    # Load and update workflow
    prompt = load_workflow(workflow_file, config)
    
    # Upload image with overwrite=True to ensure we're using the latest version
    upload_result = upload_image(image_path, "current_frame.png", config, overwrite=True)
    image_name = upload_result['name']
    print(f"Image uploaded successfully: {image_name}")

    prev_frame_name = None
    if prev_frame_path:
        upload_result = upload_image(prev_frame_path, "prev_frame.png", config, overwrite=True)
        prev_frame_name = upload_result['name']
        print(f"Previous frame uploaded successfully: {prev_frame_name}")
    
    # Update workflow with uploaded image
    prompt = update_workflow_with_image(prompt, image_name, prev_frame_name)
    
    # Process workflow
    images = get_images(prompt, config)
    
    # Save output image
    output_path = None
    for node_id, node_images in images.items():
        if node_images:
            image = Image.open(io.BytesIO(node_images[0]))
            
            # Resize image if it exceeds max dimensions
            if config['image']['max_size'] > 0:
                width, height = image.size
                if width > config['image']['max_size'] or height > config['image']['max_size']:
                    ratio = config['image']['max_size'] / max(width, height)
                    new_size = (int(width * ratio), int(height * ratio))
                    image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            output_filename = f"{os.path.splitext(workflow_file)[0]}_{os.path.splitext(os.path.basename(image_path))[0]}.png"
            output_path = os.path.join(output_dir, config['directories']['output_subfolders']['images'], output_filename)
            image.save(output_path, quality=config['image']['quality'])
            print(f"Image saved as {output_filename}")
            break
    
    return output_path

def extract_frames(video_path, temp_dir, config):
    """Extract frames from video file."""
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    
    # Skip the specified number of frames at the start
    skip_frames = config['video'].get('skip_first_frames', 0)
    for _ in range(skip_frames):
        cap.read()
    total_frames = max(0, total_frames - skip_frames)
    
    # Calculate how many frames to process
    select_every_n = config['video']['select_every_n']
    max_frames = config['video']['max_frames']
    frames_to_process = min(total_frames // select_every_n, max_frames)
    
    if frames_to_process <= 0:
        print(f"Warning: No frames to process in video {video_path} after skipping {skip_frames} frames")
        cap.release()
        return [], 0
    
    frame_paths = []
    with tqdm(total=frames_to_process, desc="Extracting frames") as pbar:
        frame_count = 0
        processed_count = 0
        
        while frame_count < total_frames and processed_count < frames_to_process:
            ret, frame = cap.read()
            if not ret:
                break
                
            if frame_count % select_every_n == 0:
                frame_path = os.path.join(temp_dir, f"frame_{processed_count:04d}.png")
                cv2.imwrite(frame_path, frame)
                frame_paths.append(frame_path)
                processed_count += 1
                pbar.update(1)
            
            frame_count += 1
    
    cap.release()
    return frame_paths, fps

def process_video(workflow_file, video_path, output_dir, config):
    """Process a video through a workflow by splitting it into frames."""
    print(f"\nProcessing video with workflow: {workflow_file}")
    print(f"Using video: {video_path}")
    
    # Create temporary directory for frames
    temp_dir = os.path.join(output_dir, config['video']['temp_dir'])
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Extract frames and get original FPS
        frames, original_fps = extract_frames(video_path, temp_dir, config)
        processed_frames = []
        
        if not frames:
            print(f"No frames extracted from {video_path}")
            return None
            
        print(f"Source video has {original_fps} FPS")
        
        # Process each frame
        print("Processing frames through workflow...")
        prev_frame_path = None  # Initialize previous frame path
        for i, frame_path in enumerate(tqdm(frames)):
            # For the first frame, create a black frame with same dimensions
            if i == 0:
                # Read first frame to get dimensions
                first_frame = cv2.imread(frame_path)
                height, width = first_frame.shape[:2]
                # Create black frame
                black_frame = np.zeros((height, width, 3), dtype=np.uint8)
                black_frame_path = os.path.join(temp_dir, "black_frame.png")
                cv2.imwrite(black_frame_path, black_frame)
                prev_frame_path = black_frame_path
            else:
                # Use the previous raw frame
                prev_frame_path = frames[i-1]

            output_path = process_workflow(workflow_file, frame_path, prev_frame_path, output_dir, config)
            if output_path:
                processed_frames.append(output_path)
        
        # Create output video
        if processed_frames:
            output_filename = f"{os.path.splitext(workflow_file)[0]}_{os.path.splitext(os.path.basename(video_path))[0]}.mp4"
            output_video_path = os.path.join(output_dir, config['directories']['output_subfolders']['videos'], output_filename)
            
            # Read first frame to get dimensions
            first_frame = cv2.imread(processed_frames[0])
            height, width = first_frame.shape[:2]
            
            # Use the original video's FPS (or config fps as fallback)
            output_fps = original_fps if original_fps > 0 else config['video']['fps']
            print(f"Creating output video with {output_fps} FPS (matching source video)")
            
            # Create video writer with H.264 codec for better browser compatibility
            try:
                fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264 codec (also known as avc1)
                if not os.path.exists(os.path.dirname(output_video_path)):
                    os.makedirs(os.path.dirname(output_video_path), exist_ok=True)
                
                out = cv2.VideoWriter(output_video_path, fourcc, output_fps, (width, height))
                if not out.isOpened():
                    # Try with a different codec if avc1 fails
                    print(f"Warning: Failed to create video with avc1 codec, trying mp4v instead")
                    out.release()
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    out = cv2.VideoWriter(output_video_path, fourcc, output_fps, (width, height))
                
                print("Creating output video...")
                for frame_path in tqdm(processed_frames):
                    frame = cv2.imread(frame_path)
                    out.write(frame)
                
                out.release()
                
                # Verify the video was created successfully
                if os.path.exists(output_video_path) and os.path.getsize(output_video_path) > 0:
                    print(f"Video saved as {output_filename} ({os.path.getsize(output_video_path)} bytes)")
                    return output_video_path
                else:
                    print(f"Error: Failed to create video file {output_filename}")
                    return None
            except Exception as e:
                print(f"Error creating video: {str(e)}")
                return None
    
    finally:
        # Clean up temporary directory
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)
    
    return None

def is_video_file(file_path):
    """Check if a file is a video based on its extension."""
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
    return os.path.splitext(file_path.lower())[1] in video_extensions

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Process workflows with images and videos')
    parser.add_argument('--config', required=True, help='Path to configuration file')
    parser.add_argument('--html-only', action='store_true', help='Only generate HTML report from existing output directory')
    parser.add_argument('--output-dir', help='Specify output directory for HTML-only mode')
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    if args.html_only:
        # HTML-only mode
        if not args.output_dir:
            print("Error: --output-dir is required with --html-only")
            sys.exit(1)
            
        output_dir = args.output_dir
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if not os.path.exists(output_dir):
            print(f"Error: Output directory '{output_dir}' does not exist")
            sys.exit(1)
            
        print(f"Generating HTML report for existing output directory: {output_dir}")
        
        # Check for required subdirectories
        images_dir = os.path.join(output_dir, config['directories']['output_subfolders']['images'])
        videos_dir = os.path.join(output_dir, config['directories']['output_subfolders']['videos'])
        inputs_dir = os.path.join(output_dir, config['directories']['output_subfolders']['inputs'])
        workflows_dir = os.path.join(output_dir, config['directories']['output_subfolders']['workflows'])
        
        if not all(os.path.exists(d) for d in [images_dir, videos_dir, inputs_dir, workflows_dir]):
            print("Warning: Some required subdirectories are missing. The HTML report may be incomplete.")
        
        # Collect all existing files
        workflow_copies = glob.glob(os.path.join(workflows_dir, "*.json"))
        input_images = [f for f in glob.glob(os.path.join(inputs_dir, "*.*")) if not is_video_file(f)]
        input_videos = [f for f in glob.glob(os.path.join(inputs_dir, "*.*")) if is_video_file(f)]
        all_output_paths = glob.glob(os.path.join(images_dir, "*.png"))
        all_video_paths = glob.glob(os.path.join(videos_dir, "*.mp4"))
        
        # Extract workflow names
        workflow_names = [os.path.basename(wf) for wf in workflow_copies]
        
        # Create HTML table
        if (all_output_paths and input_images) or (all_video_paths and input_videos):
            html_path = create_html_table(output_dir, all_output_paths, workflow_names, 
                                        input_images, all_video_paths, workflow_copies, config, timestamp)
            print(f"HTML table saved as: {html_path}")
            
            # Copy CSS file to output directory if it doesn't exist
            css_source = os.path.join(os.path.dirname(__file__), 'report.css')
            css_dest = os.path.join(output_dir, 'report.css')
            if os.path.exists(css_source) and not os.path.exists(css_dest):
                shutil.copy2(css_source, output_dir)
        else:
            print("No output files found to generate HTML report")
            
    else:
        # Normal processing mode
        # Create output directory
        output_dir, timestamp = create_output_directory(config)
        print(f"Created output directory: {output_dir}")
        
        # Get all workflow files
        workflow_files = glob.glob(os.path.join(config['directories']['workflows'], config['workflow']['pattern']))
        workflow_files.sort()
        
        # Copy workflow files to the workflows subdirectory
        workflow_copies = copy_workflow_files(workflow_files, output_dir, config)
        
        # Get all input files (both images and videos)
        input_files = glob.glob(os.path.join(config['directories']['input_images'], "*.*"))
        input_files.sort()
        
        # Separate images and videos
        input_images = [f for f in input_files if not is_video_file(f)]
        input_videos = [f for f in input_files if is_video_file(f)]

        print(f"Input images: {input_images}")
        print(f"Input videos: {input_videos}")
        
        # Copy input images and videos to the inputs subdirectory
        input_copies = copy_input_images(input_images + input_videos, output_dir, config)
        
        # Process each workflow with each image/video
        all_output_paths = []
        all_video_paths = []
        workflow_names = []

        print(f"Workflow files: {workflow_files}")
        
        for workflow_file in workflow_files:
            workflow_name = os.path.basename(workflow_file)
            workflow_names.append(workflow_name)

            print(f"Processing workflow: {workflow_name}")
            
            # Process images
            for image_path in input_images:
                output_path = process_workflow(workflow_name, image_path, None, output_dir, config)
                if output_path:
                    all_output_paths.append(output_path)
            
            # Process videos
            for video_path in input_videos:
                output_path = process_video(workflow_name, video_path, output_dir, config)
                if output_path:
                    all_video_paths.append(output_path)
                    print(f"Video processing complete: {output_path}")
        
        # Create comparison grid and HTML table
        if (all_output_paths and input_images) or (all_video_paths and input_videos):
            if config['output']['create_grid'] and all_output_paths:
                grid_path = create_comparison_grid(output_dir, all_output_paths, workflow_names, input_copies[:len(input_images)], config, timestamp)
                print(f"\nComparison grid saved as: {grid_path}")
            
            if config['output']['create_html']:
                html_path = create_html_table(output_dir, all_output_paths, workflow_names, 
                                            input_copies[:len(input_images)], all_video_paths, workflow_copies, config, timestamp)
                print(f"HTML table saved as: {html_path}")
        
        # Create zip archive of results
        zip_path = create_zip_archive(output_dir, timestamp)
        print(f"\nResults archived as: {zip_path}")

if __name__ == "__main__":
    main() 