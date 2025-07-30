import cv2
import mediapipe as mp
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.pyplot as plt
import numpy as np
import concurrent.futures

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Init MediaPipe modules
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
mp_holistic = mp.solutions.holistic
mp_face_mesh = mp.solutions.face_mesh

# Initialize Matplotlib for 3D plotting
def init_3d_plot(parent):
    fig = Figure()
    ax = fig.add_subplot(111, projection='3d')
    scatter_dict = {}

    canvas = FigureCanvasTkAgg(fig, master=parent)
    canvas.draw()
    canvas_widget = canvas.get_tk_widget()

    return fig, ax, scatter_dict, canvas, canvas_widget


def update_3d_plot(ax, scatter_dict, coord_dict, canvas_obj):
    ax.clear()

    # Axes settings
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_zlim(-1.0, 1.0)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.set_title("3D Body + Hands")

    # Debug: Print pose coords
    pose = coord_dict.get('pose', {})

    """ for idx, (x, y, z) in pose.items():
        print(f"  ID {idx}: x={x:.2f}, y={y:.2f}, z={z:.2f}") """

    # Plot scatter points with flipped Y and Z
    def plot_points(label, coords, color='b'):
        if coords:
            flipped_coords = []
            for x, y, z in coords.values():
                if not any(np.isnan([x, y, z])):
                    flipped_coords.append((x, 1 - y, -z))
            if flipped_coords:
                xs, ys, zs = zip(*flipped_coords)
                scatter_dict[label] = ax.scatter(xs, ys, zs, label=label, s=30, color=color)

    plot_points('pose', pose, color='orange')
    plot_points('left_hand', coord_dict.get('left_hand', {}), color='green')
    plot_points('right_hand', coord_dict.get('right_hand', {}), color='blue')

    # Connect joints using flipped Y and Z
    def connect(group, idx1, idx2):
        if idx1 in group and idx2 in group:
            x1, y1, z1 = group[idx1]
            x2, y2, z2 = group[idx2]
            if not any(np.isnan([x1, y1, z1, x2, y2, z2])):
                ax.plot([x1, x2], [1 - y1, 1 - y2], [-z1, -z2], color='gray', linewidth=2)

    def connect_between(group1, idx1, group2, idx2):
        if idx1 in group1 and idx2 in group2:
            x1, y1, z1 = group1[idx1]
            x2, y2, z2 = group2[idx2]
            if not any(np.isnan([x1, y1, z1, x2, y2, z2])):
                ax.plot([x1, x2], [1 - y1, 1 - y2], [-z1, -z2], color='gray', linewidth=2)

    lh = coord_dict.get('left_hand', {})
    rh = coord_dict.get('right_hand', {})

    # Pose connections
    connect(pose, 11, 13)  # Left shoulder to elbow
    connect_between(pose, 13, lh, 0)  # Left elbow to left wrist

    connect(pose, 12, 14)  # Right shoulder to elbow
    connect_between(pose, 14, rh, 0)  # Right elbow to right wrist

    # Optional: connect shoulders to hips for better orientation
    connect(pose, 11, 23)  # Left shoulder to hip
    connect(pose, 12, 24)  # Right shoulder to hip
    
    # Left hand connections
    connect(lh, 0, 5)   # Wrist to Index MCP
    connect(lh, 0, 9)   # Wrist to Middle MCP
    connect(lh, 0, 13)  # Wrist to Ring MCP
    connect(lh, 0, 17)  # Wrist to Pinky MCP

    connect(lh, 5, 6)
    connect(lh, 6, 7)
    connect(lh, 7, 8)

    connect(lh, 9, 10)
    connect(lh, 10, 11)
    connect(lh, 11, 12)

    connect(lh, 13, 14)
    connect(lh, 14, 15)
    connect(lh, 15, 16)

    connect(lh, 17, 18)
    connect(lh, 18, 19)
    connect(lh, 19, 20)

    # Right hand connections
    connect(rh, 0, 5)
    connect(rh, 0, 9)
    connect(rh, 0, 13)
    connect(rh, 0, 17)

    connect(rh, 5, 6)
    connect(rh, 6, 7)
    connect(rh, 7, 8)

    connect(rh, 9, 10)
    connect(rh, 10, 11)
    connect(rh, 11, 12)

    connect(rh, 13, 14)
    connect(rh, 14, 15)
    connect(rh, 15, 16)

    connect(rh, 17, 18)
    connect(rh, 18, 19)
    connect(rh, 19, 20)

    canvas_obj.draw()


def get_selected_coords_for_3d_plot(results):
    coord_dict = {
        'pose': {},
        'left_hand': {},
        'right_hand': {}
    }

    # --- Pose landmarks: shoulders, elbows, hips ---
    if results.pose_landmarks:
        for idx in [11, 12, 13, 14, 23, 24]:
            lm = results.pose_landmarks.landmark[idx]
            coord_dict['pose'][idx] = (lm.x, lm.y, lm.z)

    # --- Hand landmark indices ---
    wrist_id = 0
    mcp_ids = [2, 5, 9, 13, 17]
    pip_ids = [3, 6, 10, 14, 18]

    # --- Left Hand ---
    if results.left_hand_landmarks:
        for idx in [wrist_id] + mcp_ids + pip_ids:
            lm = results.left_hand_landmarks.landmark[idx]
            coord_dict['left_hand'][idx] = (lm.x, lm.y, lm.z)

    # --- Right Hand ---
    if results.right_hand_landmarks:
        for idx in [wrist_id] + mcp_ids + pip_ids:
            lm = results.right_hand_landmarks.landmark[idx]
            coord_dict['right_hand'][idx] = (lm.x, lm.y, lm.z)

    return coord_dict


def draw_selected_dots(image, results):
    h, w, _ = image.shape
    coord_dict = {
        'pose': {},
        'left_hand': {},
        'right_hand': {}
    }

    # --- Pose: shoulders, elbows, hips ---
    if results.pose_landmarks:
        for idx in [11, 12, 13, 14, 23, 24]:
            lm = results.pose_landmarks.landmark[idx]
            cx, cy = int(lm.x * w), int(lm.y * h)
            coord_dict['pose'][idx] = (cx, cy)
            cv2.circle(image, (cx, cy), 8, (0, 255, 255), -1)

    wrist_id = 0
    mcp_ids = [2, 5, 9, 13, 17]
    pip_ids = [3, 6, 10, 14, 18]

    # --- Left Hand ---
    if results.left_hand_landmarks:
        for idx in [wrist_id] + mcp_ids + pip_ids:
            lm = results.left_hand_landmarks.landmark[idx]
            cx, cy = int(lm.x * w), int(lm.y * h)
            coord_dict['left_hand'][idx] = (cx, cy)
            cv2.circle(image, (cx, cy), 8, (255, 255, 0), -1)

        # Arm lines
        if 11 in coord_dict['pose'] and 13 in coord_dict['pose']:
            cv2.line(image, coord_dict['pose'][11], coord_dict['pose'][13], (0, 128, 255), 2)
        if 13 in coord_dict['pose'] and 0 in coord_dict['left_hand']:
            cv2.line(image, coord_dict['pose'][13], coord_dict['left_hand'][0], (0, 0, 255), 2)

        # Hand lines
        for mcp_id in mcp_ids:
            if wrist_id in coord_dict['left_hand'] and mcp_id in coord_dict['left_hand']:
                cv2.line(image, coord_dict['left_hand'][wrist_id], coord_dict['left_hand'][mcp_id], (255, 255, 0), 2)
        for mcp_id, pip_id in zip(mcp_ids, pip_ids):
            if mcp_id in coord_dict['left_hand'] and pip_id in coord_dict['left_hand']:
                cv2.line(image, coord_dict['left_hand'][mcp_id], coord_dict['left_hand'][pip_id], (255, 255, 0), 2)

        if 11 in coord_dict['pose'] and 23 in coord_dict['pose']:
            cv2.line(image, coord_dict['pose'][11], coord_dict['pose'][23], (144, 238, 144), 2)

    # --- Right Hand ---
    if results.right_hand_landmarks:
        for idx in [wrist_id] + mcp_ids + pip_ids:
            lm = results.right_hand_landmarks.landmark[idx]
            cx, cy = int(lm.x * w), int(lm.y * h)
            coord_dict['right_hand'][idx] = (cx, cy)
            cv2.circle(image, (cx, cy), 8, (255, 255, 0), -1)

        if 12 in coord_dict['pose'] and 14 in coord_dict['pose']:
            cv2.line(image, coord_dict['pose'][12], coord_dict['pose'][14], (0, 128, 255), 2)
        if 14 in coord_dict['pose'] and 0 in coord_dict['right_hand']:
            cv2.line(image, coord_dict['pose'][14], coord_dict['right_hand'][0], (0, 0, 255), 2)

        for mcp_id in mcp_ids:
            if wrist_id in coord_dict['right_hand'] and mcp_id in coord_dict['right_hand']:
                cv2.line(image, coord_dict['right_hand'][wrist_id], coord_dict['right_hand'][mcp_id], (255, 255, 0), 2)
        for mcp_id, pip_id in zip(mcp_ids, pip_ids):
            if mcp_id in coord_dict['right_hand'] and pip_id in coord_dict['right_hand']:
                cv2.line(image, coord_dict['right_hand'][mcp_id], coord_dict['right_hand'][pip_id], (255, 255, 0), 2)

        if 12 in coord_dict['pose'] and 24 in coord_dict['pose']:
            cv2.line(image, coord_dict['pose'][12], coord_dict['pose'][24], (144, 238, 144), 2)

    return coord_dict

def calculate_angle(v1, v2):
    dot = np.dot(v1, v2)
    norms = np.linalg.norm(v1) * np.linalg.norm(v2)

    if norms == 0:
        return 0.0  # Avoid division by zero

    cosine_angle = np.clip(dot / norms, -1.0, 1.0)
    angle_rad = np.arccos(cosine_angle)
    angle_deg = np.degrees(angle_rad)
    return angle_deg  # In degrees


def project_vector(v, onto):
    onto_unit = onto / np.linalg.norm(onto)
    return np.dot(v, onto_unit) * onto_unit


def calculate_left_shoulder_servo_1(coord):
    
    # Check for required keys in advance
    required_pose_keys = [11, 13, 23]
    required_hand_keys = [0, 5, 9, 17]
    
    if not all(k in coord['pose'] for k in required_pose_keys):
        print("[WARN] Missing one or more pose landmarks for shoulder servo 1")
        return None
    if not all(k in coord['left_hand'] for k in required_hand_keys):
        print("[WARN] Missing one or more left hand landmarks for shoulder servo 1")
        return None
    
    # Pose landmarks
    left_shoulder = np.array(coord['pose'][11])
    left_elbow = np.array(coord['pose'][13])
    left_hip = np.array(coord['pose'][23])
    left_imaginary_point = np.array([left_hip[0], left_elbow[1], left_elbow[2]])
    
    # Hand landmarks
    left_wrist = np.array(coord['left_hand'][0])
    left_middle_finger_mcp = np.array(coord['left_hand'][9])
    left_index_finger_mcp = np.array(coord['left_hand'][5])
    left_pinky_mcp = np.array(coord['left_hand'][17])
    
    # Vectors     
    left_forearm_vector = left_wrist - left_elbow
    if np.linalg.norm(left_forearm_vector) == 0:
        print("[WARN] Zero-length forearm vector")
        return None
    
    
    vec1 = left_imaginary_point - left_shoulder
    vec2 = left_hip - left_shoulder
    
    if np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0:
        print("[WARN] Zero-length vector for angle calculation")
        return None

    left_alpha = calculate_angle(vec1, vec2)
    return left_alpha


def calculate_left_shoulder_servo_2(coord):
     # Check for required landmarks
    required_pose_keys = [11, 13, 23]
    required_hand_keys = [0, 5, 9, 17]

    if not all(k in coord['pose'] for k in required_pose_keys):
        print("[WARN] Missing one or more pose landmarks for shoulder servo 2")
        return None
    if not all(k in coord['left_hand'] for k in required_hand_keys):
        print("[WARN] Missing one or more left hand landmarks for shoulder servo 2")
        return None

    # Pose landmarks
    left_shoulder = np.array(coord['pose'][11])
    left_elbow = np.array(coord['pose'][13])
    left_hip = np.array(coord['pose'][23])
    left_imaginary_point = np.array([left_hip[0], left_elbow[1], left_elbow[2]])
    

    vec1 = left_imaginary_point - left_shoulder
    vec2 = left_elbow - left_shoulder

    if np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0:
        print("[WARN] Zero-length vector in shoulder servo 2")
        return None

    return calculate_angle(vec1, vec2)


def calculate_left_shoulder_servo_3(coord):
    
    # Check for required landmarks
    required_pose_keys = [11, 13, 23]
    required_hand_keys = [0, 5, 9, 17]

    if not all(k in coord['pose'] for k in required_pose_keys):
        print("[WARN] Missing one or more pose landmarks for shoulder servo 3")
        return None
    if not all(k in coord['left_hand'] for k in required_hand_keys):
        print("[WARN] Missing one or more left hand landmarks for shoulder servo 3")
        return None
    
    
    # Pose landmarks
    left_shoulder = np.array(coord['pose'][11])
    right_shoulder = np.array(coord['pose'][12])
    left_elbow = np.array(coord['pose'][13])
    left_hip = np.array(coord['pose'][23])
    left_imaginary_point = np.array([left_hip[0], left_elbow[1], left_elbow[2]])
    
    # Hand landmarks
    left_wrist = np.array(coord['left_hand'][0])
    left_middle_finger_mcp = np.array(coord['left_hand'][9])
    left_index_finger_mcp = np.array(coord['left_hand'][5])
    left_pinky_mcp = np.array(coord['left_hand'][17])
    
    left_upper_arm_vector = left_elbow - left_shoulder
    left_forearm_vector = left_wrist - left_elbow
    chest_vector = right_shoulder - left_shoulder
    
    left_forearm_projection = project_vector(left_forearm_vector, left_upper_arm_vector)
    left_forearm_perpendicular_vector = left_forearm_vector - left_forearm_projection
    
    left_ref_raw = np.cross(chest_vector, left_upper_arm_vector)
    left_ref_proj = project_vector(left_ref_raw, left_upper_arm_vector)
    left_shoulder_twist_ref = left_ref_raw - left_ref_proj
          
    if np.linalg.norm(left_forearm_perpendicular_vector) == 0 or np.linalg.norm(left_shoulder_twist_ref) == 0:
        print("[WARN] Zero-length vector in shoulder servo 3")
        return None
    
    return calculate_angle(left_forearm_perpendicular_vector, left_shoulder_twist_ref)






def calculate_left_elbow_servo_1(coord):
    # Check for required landmarks
    required_pose_keys = [11, 13, 23]
    required_hand_keys = [0, 5, 9, 17]

    if not all(k in coord['pose'] for k in required_pose_keys):
        print("[WARN] Missing one or more pose landmarks for elbow servo 1")
        return None
    if not all(k in coord['left_hand'] for k in required_hand_keys):
        print("[WARN] Missing one or more left hand landmarks for elbow servo 1")
        return None

    # Pose landmarks
    left_shoulder = np.array(coord['pose'][11])
    right_shoulder = np.array(coord['pose'][12])
    left_elbow = np.array(coord['pose'][13])
    left_hip = np.array(coord['pose'][23])
    left_imaginary_point = np.array([left_hip[0], left_elbow[1], left_elbow[2]])
    
    # Hand landmarks
    left_wrist = np.array(coord['left_hand'][0])
    left_middle_finger_mcp = np.array(coord['left_hand'][9])
    left_index_finger_mcp = np.array(coord['left_hand'][5])
    left_pinky_mcp = np.array(coord['left_hand'][17])
    
    left_forearm_vector = left_wrist - left_elbow
    left_hand_direction_vector = left_middle_finger_mcp - left_wrist
    left_forearm_unit_vector = left_forearm_vector / np.linalg.norm(left_forearm_vector)
    
    
    if np.linalg.norm(left_hand_direction_vector) == 0 or np.linalg.norm(left_forearm_unit_vector) == 0:
        print("[WARN] Zero-length vector in left elbow servo 1")
        return None

    return calculate_angle(left_hand_direction_vector, left_forearm_unit_vector)


def calculate_left_elbow_servo_2(coord):
    # Check for required landmarks
    required_pose_keys = [11, 13, 23]
    required_hand_keys = [0, 5, 9, 17]

    if not all(k in coord['pose'] for k in required_pose_keys):
        print("[WARN] Missing one or more pose landmarks for elbow servo 2")
        return None
    if not all(k in coord['left_hand'] for k in required_hand_keys):
        print("[WARN] Missing one or more left hand landmarks for elbow servo 2")
        return None
    
    
    # Pose landmarks
    left_shoulder = np.array(coord['pose'][11])
    right_shoulder = np.array(coord['pose'][12])
    left_elbow = np.array(coord['pose'][13])
    left_hip = np.array(coord['pose'][23])
    left_imaginary_point = np.array([left_hip[0], left_elbow[1], left_elbow[2]])
    
    # Hand landmarks
    left_wrist = np.array(coord['left_hand'][0])
    left_middle_finger_mcp = np.array(coord['left_hand'][9])
    left_index_finger_mcp = np.array(coord['left_hand'][5])
    left_pinky_mcp = np.array(coord['left_hand'][17])
    
    # Vectors
    left_forearm_vector = left_wrist - left_elbow
    left_forearm_unit_vector = left_forearm_vector / np.linalg.norm(left_forearm_vector)
    left_palm_vector = left_index_finger_mcp - left_pinky_mcp
    left_palm_vector_perpendicular_vector = left_palm_vector - (np.dot(left_palm_vector, left_forearm_unit_vector) * left_forearm_unit_vector)
    
    
    if np.linalg.norm(left_palm_vector) == 0 or np.linalg.norm(left_palm_vector_perpendicular_vector) == 0:
        print("[WARN] Zero-length vector in left elbow servo 2")
        return None

    return calculate_angle(left_palm_vector, left_palm_vector_perpendicular_vector)


def left_hand_servo_thumb(coord):
    
    # Check for required landmarks
    required_hand_keys = [0, 2, 3, 5, 6, 9, 10, 13, 14, 17, 18]

    if not all(k in coord['left_hand'] for k in required_hand_keys):
        print("[WARN] Missing one or more left hand landmarks for shoulder servo 2")
        return None
    
    # Hand landmarks
    left_wrist = np.array(coord['left_hand'][0])
    
    left_thumb_finger_mcp = np.array(coord['left_hand'][2])
    left_index_finger_mcp = np.array(coord['left_hand'][5])
    left_middle_finger_mcp = np.array(coord['left_hand'][9])
    left_ring_finger_mcp = np.array(coord['left_hand'][13])
    left_pinky_finger_mcp = np.array(coord['left_hand'][17])
    
    left_thumb_finger_pip = np.array(coord['left_hand'][3])
    left_index_finger_pip = np.array(coord['left_hand'][6])
    left_middle_finger_pip = np.array(coord['left_hand'][10])
    left_ring_finger_pip = np.array(coord['left_hand'][14])
    left_pinky_finger_pip = np.array(coord['left_hand'][18])
    
    left_thumb_vector = left_thumb_finger_pip - left_thumb_finger_mcp
    left_thumb_palm_vector = left_thumb_finger_mcp - left_wrist

    return calculate_angle(left_thumb_vector, left_thumb_palm_vector)

def left_hand_servo_index(coord):
    
    # Check for required landmarks
    required_hand_keys = [0, 2, 3, 5, 6, 9, 10, 13, 14, 17, 18]

    if not all(k in coord['left_hand'] for k in required_hand_keys):
        print("[WARN] Missing one or more left hand landmarks for shoulder servo 2")
        return None
    
    # Hand landmarks
    left_wrist = np.array(coord['left_hand'][0])
    
    left_thumb_finger_mcp = np.array(coord['left_hand'][2])
    left_index_finger_mcp = np.array(coord['left_hand'][5])
    left_middle_finger_mcp = np.array(coord['left_hand'][9])
    left_ring_finger_mcp = np.array(coord['left_hand'][13])
    left_pinky_finger_mcp = np.array(coord['left_hand'][17])
    
    left_thumb_finger_pip = np.array(coord['left_hand'][3])
    left_index_finger_pip = np.array(coord['left_hand'][6])
    left_middle_finger_pip = np.array(coord['left_hand'][10])
    left_ring_finger_pip = np.array(coord['left_hand'][14])
    left_pinky_finger_pip = np.array(coord['left_hand'][18])
    
    left_index_vector = left_index_finger_pip - left_index_finger_mcp
    left_index_palm_vector = left_index_finger_mcp - left_wrist

    return calculate_angle(left_index_vector, left_index_palm_vector)

def left_hand_servo_middle(coord):
    # Check for required landmarks
    required_hand_keys = [0, 2, 3, 5, 6, 9, 10, 13, 14, 17, 18]

    if not all(k in coord['left_hand'] for k in required_hand_keys):
        print("[WARN] Missing one or more left hand landmarks for shoulder servo 2")
        return None
    
    # Hand landmarks
    left_wrist = np.array(coord['left_hand'][0])
    
    left_thumb_finger_mcp = np.array(coord['left_hand'][2])
    left_index_finger_mcp = np.array(coord['left_hand'][5])
    left_middle_finger_mcp = np.array(coord['left_hand'][9])
    left_ring_finger_mcp = np.array(coord['left_hand'][13])
    left_pinky_finger_mcp = np.array(coord['left_hand'][17])
    
    left_thumb_finger_pip = np.array(coord['left_hand'][3])
    left_index_finger_pip = np.array(coord['left_hand'][6])
    left_middle_finger_pip = np.array(coord['left_hand'][10])
    left_ring_finger_pip = np.array(coord['left_hand'][14])
    left_pinky_finger_pip = np.array(coord['left_hand'][18])
    
    left_middle_vector = left_middle_finger_pip - left_middle_finger_mcp
    left_middle_palm_vector = left_middle_finger_mcp - left_wrist

    return calculate_angle(left_middle_vector, left_middle_palm_vector)

def left_hand_servo_ring(coord):
    # Check for required landmarks
    required_hand_keys = [0, 2, 3, 5, 6, 9, 10, 13, 14, 17, 18]

    if not all(k in coord['left_hand'] for k in required_hand_keys):
        print("[WARN] Missing one or more left hand landmarks for shoulder servo 2")
        return None
    
    # Hand landmarks
    left_wrist = np.array(coord['left_hand'][0])
    
    left_thumb_finger_mcp = np.array(coord['left_hand'][2])
    left_index_finger_mcp = np.array(coord['left_hand'][5])
    left_middle_finger_mcp = np.array(coord['left_hand'][9])
    left_ring_finger_mcp = np.array(coord['left_hand'][13])
    left_pinky_finger_mcp = np.array(coord['left_hand'][17])
    
    left_thumb_finger_pip = np.array(coord['left_hand'][3])
    left_index_finger_pip = np.array(coord['left_hand'][6])
    left_middle_finger_pip = np.array(coord['left_hand'][10])
    left_ring_finger_pip = np.array(coord['left_hand'][14])
    left_pinky_finger_pip = np.array(coord['left_hand'][18])
    
    left_ring_vector = left_ring_finger_pip - left_ring_finger_mcp
    left_ring_palm_vector = left_ring_finger_mcp - left_wrist

    return calculate_angle(left_ring_vector, left_ring_palm_vector)

def left_hand_servo_pinky(coord):
    # Check for required landmarks
    required_hand_keys = [0, 2, 3, 5, 6, 9, 10, 13, 14, 17, 18]

    if not all(k in coord['left_hand'] for k in required_hand_keys):
        print("[WARN] Missing one or more left hand landmarks for shoulder servo 2")
        return None
    
    # Hand landmarks
    left_wrist = np.array(coord['left_hand'][0])
    
    left_thumb_finger_mcp = np.array(coord['left_hand'][2])
    left_index_finger_mcp = np.array(coord['left_hand'][5])
    left_middle_finger_mcp = np.array(coord['left_hand'][9])
    left_ring_finger_mcp = np.array(coord['left_hand'][13])
    left_pinky_finger_mcp = np.array(coord['left_hand'][17])
    
    left_thumb_finger_pip = np.array(coord['left_hand'][3])
    left_index_finger_pip = np.array(coord['left_hand'][6])
    left_middle_finger_pip = np.array(coord['left_hand'][10])
    left_ring_finger_pip = np.array(coord['left_hand'][14])
    left_pinky_finger_pip = np.array(coord['left_hand'][18])
    
    left_pinky_vector = left_pinky_finger_pip - left_pinky_finger_mcp
    left_pinky_palm_vector = left_pinky_finger_mcp - left_wrist

    return calculate_angle(left_pinky_vector, left_pinky_palm_vector)

