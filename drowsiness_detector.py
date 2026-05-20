import cv2
import mediapipe as mp
import numpy as np
import time
import csv
import os
import subprocess
import platform
from datetime import datetime
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import threading
from flask import Flask, jsonify
import logging

# Configuração do Flask e Estado Compartilhado
app = Flask(__name__)
# Desativa logs repetitivos do Flask para manter o console CLI perfeitamente limpo
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

shared_state = {
    "ear": 0.35,
    "mar": 0.15,
    "yaw": 0.0,
    "pitch": 0.0,
    "is_drowsy": False,
    "is_yawn": False,
    "is_distracted": False,
    "drowsy_count": 0,
    "yawn_count": 0,
    "distracted_count": 0,
    "elapsed_drowsy": 0.0,
    "elapsed_yawn": 0.0,
    "elapsed_distracted": 0.0,
    "face_detected": False,
    "status": "ATENTO"
}


@app.route("/")
def serve_dashboard():
    try:
        # Lê e serve o painel HTML em tempo real da raiz do projeto
        with open("dashboard.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Erro ao abrir o dashboard.html: {str(e)}", 500

@app.route("/api/state")
def get_realtime_state():
    return jsonify(shared_state)

@app.route("/api/events")
def get_historical_events():
    events = []
    if os.path.exists("drowsiness_events.csv"):
        try:
            with open("drowsiness_events.csv", mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    events.append(row)
        except Exception:
            pass
    return jsonify(events)

def run_flask_server():
    # Inicia o servidor local de forma limpa na porta 55800
    try:
        app.run(host="0.0.0.0", port=55800, debug=False, use_reloader=False)
    except Exception as e:
        print(f"\n[ERRO] Nao foi possivel iniciar o servidor web na porta 55800: {e}")

# Model and audio paths
MODEL_PATH = "face_landmarker.task"
ALARM_PATH = "assets/alarm.wav"
YAWN_PATH = "assets/yawn_warning.wav"
DISTRACTION_PATH = "assets/distraction_warning.wav"

class SoundManager:
    """
    Manages audio alert playback, with a robust fallback to native macOS 'afplay'
    if pygame.mixer is unavailable (a common issue with macOS source compiles of pygame).
    """
    def __init__(self):
        self.is_mac = platform.system() == "Darwin"
        self.has_pygame_mixer = False
        self.drowsy_sound = None
        self.yawn_sound = None
        self.distraction_sound = None
        
        # Audio active processes (for macOS afplay fallback)
        self.drowsy_process = None
        self.yawn_process = None
        self.distraction_process = None
        
        try:
            import pygame
            pygame.mixer.init()
            if os.path.exists(ALARM_PATH):
                self.drowsy_sound = pygame.mixer.Sound(ALARM_PATH)
            if os.path.exists(YAWN_PATH):
                self.yawn_sound = pygame.mixer.Sound(YAWN_PATH)
            if os.path.exists(DISTRACTION_PATH):
                self.distraction_sound = pygame.mixer.Sound(DISTRACTION_PATH)
            self.has_pygame_mixer = True
            print("Sons de alerta carregados via Pygame Mixer.")
        except (ImportError, NotImplementedError, Exception) as e:
            print(f"\nAviso: Pygame Mixer nao esta disponivel ({type(e).__name__}: {e}).")
            if self.is_mac:
                print("-> Usando player nativo do macOS (afplay) como alternativa automatica. Nenhum recurso sera travado!")
            else:
                print("-> Sons desativados. Alertas visuais continuarao funcionando.")

    def play_drowsy(self):
        """Starts playing the continuous drowsiness alarm."""
        if self.has_pygame_mixer and self.drowsy_sound:
            import pygame
            channel = pygame.mixer.Channel(0)
            if not channel.get_busy():
                channel.play(self.drowsy_sound, loops=-1)
        elif self.is_mac:
            if self.drowsy_process is None or self.drowsy_process.poll() is not None:
                try:
                    self.drowsy_process = subprocess.Popen(
                        ["afplay", ALARM_PATH],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except Exception:
                    pass

    def stop_drowsy(self):
        """Stops playing the drowsiness alarm."""
        if self.has_pygame_mixer:
            import pygame
            pygame.mixer.Channel(0).stop()
        elif self.is_mac:
            if self.drowsy_process is not None and self.drowsy_process.poll() is None:
                self.drowsy_process.terminate()
                self.drowsy_process = None

    def play_yawn(self):
        """Starts playing the yawn warning sound."""
        if self.has_pygame_mixer and self.yawn_sound:
            import pygame
            channel = pygame.mixer.Channel(1)
            if not channel.get_busy():
                channel.play(self.yawn_sound)
        elif self.is_mac:
            if self.yawn_process is None or self.yawn_process.poll() is not None:
                try:
                    self.yawn_process = subprocess.Popen(
                        ["afplay", YAWN_PATH],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except Exception:
                    pass

    def stop_yawn(self):
        """Stops playing the yawn warning sound."""
        if self.has_pygame_mixer:
            import pygame
            pygame.mixer.Channel(1).stop()
        elif self.is_mac:
            if self.yawn_process is not None and self.yawn_process.poll() is None:
                self.yawn_process.terminate()
                self.yawn_process = None

    def play_distraction(self):
        """Starts playing the continuous distraction alarm."""
        if self.has_pygame_mixer and self.distraction_sound:
            import pygame
            channel = pygame.mixer.Channel(2)
            if not channel.get_busy():
                channel.play(self.distraction_sound, loops=-1)
        elif self.is_mac:
            if self.distraction_process is None or self.distraction_process.poll() is not None:
                try:
                    self.distraction_process = subprocess.Popen(
                        ["afplay", DISTRACTION_PATH],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except Exception:
                    pass

    def stop_distraction(self):
        """Stops playing the distraction alarm."""
        if self.has_pygame_mixer:
            import pygame
            pygame.mixer.Channel(2).stop()
        elif self.is_mac:
            if self.distraction_process is not None and self.distraction_process.poll() is None:
                self.distraction_process.terminate()
                self.distraction_process = None

    def cleanup(self):
        """Stops all active sounds and cleans up processes."""
        self.stop_drowsy()
        self.stop_yawn()
        self.stop_distraction()

# Initialize Sound Manager
sound_manager = SoundManager()

# MediaPipe Face Landmarker Tasks API configuration
if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Erro: O arquivo de modelo '{MODEL_PATH}' nao foi encontrado. Execute generate_audio.py ou certifique-se de baixar o modelo.")

base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    output_face_blendshapes=False,
    output_facial_transformation_matrixes=False,
    num_faces=1
)
detector = vision.FaceLandmarker.create_from_options(options)
print("Detector de Landmarker MediaPipe inicializado com sucesso!")

# Landmark Indices for EAR and MAR
LEFT_EYE_H = [33, 133]
LEFT_EYE_V = [[160, 144], [158, 153]]

RIGHT_EYE_H = [362, 263]
RIGHT_EYE_V = [[385, 380], [387, 373]]

MOUTH_H = [78, 308]
MOUTH_V = [[81, 312], [82, 311], [13, 14]]

# Detection Parameters
EAR_THRESHOLD = 0.22
MAR_THRESHOLD = 0.60
ALERT_DURATION = 1.5  # seconds

# Distraction Detection Parameters
YAW_THRESHOLD = 0.33        # |yaw| > 0.33 indicates looking sideways
PITCH_DOWN_THRESHOLD = 0.12 # pitch > 0.12 indicates looking down (cellphone)
PITCH_UP_THRESHOLD = -0.38  # pitch < -0.38 indicates looking up

# CSV Logging File
LOG_FILE = "drowsiness_events.csv"

def init_csv():
    """Initializes the CSV file with headers if it doesn't exist."""
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Event_Type", "Duration_Seconds", "Peak_Value"])
        print(f"Arquivo de log '{LOG_FILE}' criado e inicializado.")

def log_event(event_type, duration, peak_val):
    """Appends an alert event to the CSV log."""
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([now_str, event_type, round(duration, 2), round(peak_val, 3)])
        print(f"[LOG] {event_type} gravado: {duration:.2f}s | Pico: {peak_val:.3f}")
    except Exception as e:
        print(f"Erro ao salvar evento no CSV: {e}")

def get_head_yaw(landmarks):
    """
    Estimates horizontal head rotation (Yaw) using landmark 3D relative positions.
    - Canto externo do olho direito: landmark 33
    - Canto externo do olho esquerdo: landmark 263
    - Ponta do nariz: landmark 4
    Returns: yaw_score (float). Pos is left, neg is right.
    """
    lm_nose = landmarks[4]
    lm_eye_r = landmarks[33]
    lm_eye_l = landmarks[263]
    
    d_left = abs(lm_nose.x - lm_eye_r.x)
    d_right = abs(lm_nose.x - lm_eye_l.x)
    
    yaw_score = (d_left - d_right) / (d_left + d_right + 1e-6)
    return yaw_score

def get_head_pitch(landmarks):
    """
    Estimates vertical head tilt (Pitch) using landmark 3D relative positions.
    - Testa: landmark 10
    - Ponta do nariz: landmark 4
    - Queixo: landmark 152
    Returns: pitch_score (float). High positive (>0.12) is looking down.
    """
    lm_forehead = landmarks[10]
    lm_nose = landmarks[4]
    lm_chin = landmarks[152]
    
    d_top = abs(lm_nose.y - lm_forehead.y)
    d_bottom = abs(lm_chin.y - lm_nose.y)
    
    pitch_score = (d_top - d_bottom) / (d_top + d_bottom + 1e-6)
    return pitch_score

def calculate_distance(p1, p2):
    """Calculates Euclidean distance between two 3D coordinates."""
    return np.linalg.norm(np.array(p1) - np.array(p2))

def get_ear(landmarks, width, height):
    """Computes the Eye Aspect Ratio (EAR)."""
    def get_coords(idx):
        lm = landmarks[idx]
        return np.array([lm.x * width, lm.y * height])
    
    # Left Eye EAR
    p1_l, p4_l = get_coords(LEFT_EYE_H[0]), get_coords(LEFT_EYE_H[1])
    p2_l, p6_l = get_coords(LEFT_EYE_V[0][0]), get_coords(LEFT_EYE_V[0][1])
    p3_l, p5_l = get_coords(LEFT_EYE_V[1][0]), get_coords(LEFT_EYE_V[1][1])
    
    ear_left = (calculate_distance(p2_l, p6_l) + calculate_distance(p3_l, p5_l)) / (2.0 * calculate_distance(p1_l, p4_l) + 1e-6)
    
    # Right Eye EAR
    p1_r, p4_r = get_coords(RIGHT_EYE_H[0]), get_coords(RIGHT_EYE_H[1])
    p2_r, p6_r = get_coords(RIGHT_EYE_V[0][0]), get_coords(RIGHT_EYE_V[0][1])
    p3_r, p5_r = get_coords(RIGHT_EYE_V[1][0]), get_coords(RIGHT_EYE_V[1][1])
    
    ear_right = (calculate_distance(p2_r, p6_r) + calculate_distance(p3_r, p5_r)) / (2.0 * calculate_distance(p1_r, p4_r) + 1e-6)
    
    return (ear_left + ear_right) / 2.0

def get_mar(landmarks, width, height):
    """Computes the Mouth Aspect Ratio (MAR)."""
    def get_coords(idx):
        lm = landmarks[idx]
        return np.array([lm.x * width, lm.y * height])
    
    m1, m5 = get_coords(MOUTH_H[0]), get_coords(MOUTH_H[1])
    m2, m8 = get_coords(MOUTH_V[0][0]), get_coords(MOUTH_V[0][1])
    m3, m7 = get_coords(MOUTH_V[1][0]), get_coords(MOUTH_V[1][1])
    m4, m6 = get_coords(MOUTH_V[2][0]), get_coords(MOUTH_V[2][1])
    
    mar = (calculate_distance(m2, m8) + calculate_distance(m3, m7) + calculate_distance(m4, m6)) / (2.0 * calculate_distance(m1, m5) + 1e-6)
    return mar

def draw_contours(frame, landmarks, width, height, indices, color):
    """Draws points and connections on selected landmarks for visual feedback."""
    points = []
    for idx in indices:
        lm = landmarks[idx]
        pt = (int(lm.x * width), int(lm.y * height))
        points.append(pt)
        cv2.circle(frame, pt, 2, color, -1)
    
    for i in range(len(points) - 1):
        cv2.line(frame, points[i], points[i+1], color, 1)

def draw_hud(frame, ear, mar, yaw, pitch, drowsy_alert, yawn_alert, distracted_alert, drowsy_count, yawn_count, distracted_count, elapsed_drowsy, elapsed_yawn, elapsed_distracted):
    """Draws a beautiful, responsive, glassmorphism-styled HUD over the frame."""
    h, w, _ = frame.shape
    
    # Calculate scale factor relative to a baseline width of 640px
    scale = w / 640.0
    
    # Responsive component sizes
    header_h = int(85 * scale)
    sidebar_w = int(210 * scale)
    bar_w = int(120 * scale)
    bar_h = int(10 * scale)
    
    # Fonts sizes scale proportionally
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_s_title = 0.5 * scale
    font_s_value = 0.7 * scale
    font_s_sidebar_header = 0.45 * scale
    font_s_sidebar_row = 0.45 * scale
    
    # Transparent header background for stats
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, header_h), (20, 20, 24), -1)
    cv2.rectangle(overlay, (0, header_h), (w, header_h + int(5 * scale)), (0, 180, 255), -1) # Accent line
    
    # Side info card (Session stats)
    cv2.rectangle(overlay, (w - sidebar_w, header_h + int(5 * scale)), (w, header_h + int(185 * scale)), (20, 20, 24), -1)
    cv2.rectangle(overlay, (w - sidebar_w - int(4 * scale), header_h + int(5 * scale)), (w - sidebar_w, header_h + int(185 * scale)), (0, 180, 255), -1) # Vertical line
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
    
    # 1. EAR Stats & Meter
    ear_color = (0, 255, 120) if ear >= EAR_THRESHOLD else (80, 80, 255)
    cv2.putText(frame, "EAR (Olhos)", (int(20 * scale), int(30 * scale)), font, font_s_title, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(frame, f"{ear:.2f}", (int(20 * scale), int(58 * scale)), font, font_s_value, ear_color, 2, cv2.LINE_AA)
    
    # EAR visual bar
    bar_fill = int(min(1.0, ear / 0.45) * bar_w)
    cv2.rectangle(frame, (int(130 * scale), int(42 * scale)), (int(130 * scale) + bar_w, int(42 * scale) + bar_h), (50, 50, 50), -1)
    cv2.rectangle(frame, (int(130 * scale), int(42 * scale)), (int(130 * scale) + bar_fill, int(42 * scale) + bar_h), ear_color, -1)
    thresh_x = int(130 * scale) + int((EAR_THRESHOLD / 0.45) * bar_w)
    cv2.line(frame, (thresh_x, int(38 * scale)), (thresh_x, int(56 * scale)), (0, 180, 255), 1)
    
    # 2. MAR Stats & Meter
    mar_color = (0, 255, 120) if mar <= MAR_THRESHOLD else (80, 80, 255)
    cv2.putText(frame, "MAR (Boca)", (int(280 * scale), int(30 * scale)), font, font_s_title, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(frame, f"{mar:.2f}", (int(280 * scale), int(58 * scale)), font, font_s_value, mar_color, 2, cv2.LINE_AA)
    
    # MAR visual bar
    bar_fill_m = int(min(1.0, mar / 1.0) * bar_w)
    cv2.rectangle(frame, (int(390 * scale), int(42 * scale)), (int(390 * scale) + bar_w, int(42 * scale) + bar_h), (50, 50, 50), -1)
    cv2.rectangle(frame, (int(390 * scale), int(42 * scale)), (int(390 * scale) + bar_fill_m, int(42 * scale) + bar_h), mar_color, -1)
    thresh_m_x = int(390 * scale) + int((MAR_THRESHOLD / 1.0) * bar_w)
    cv2.line(frame, (thresh_m_x, int(38 * scale)), (thresh_m_x, int(56 * scale)), (0, 180, 255), 1)
    
    # 3. Sidebar Session summary
    cv2.putText(frame, "DASHBOARD SESSAO", (w - sidebar_w + int(15 * scale), header_h + int(25 * scale)), font, font_s_sidebar_header, (0, 180, 255), 2, cv2.LINE_AA)
    
    cv2.putText(frame, "Sonolencias:", (w - sidebar_w + int(15 * scale), header_h + int(55 * scale)), font, font_s_sidebar_row, (180, 180, 180), 1, cv2.LINE_AA)
    cv2.putText(frame, f"{drowsy_count}", (w - int(35 * scale), header_h + int(55 * scale)), font, font_s_sidebar_row + 0.05, (80, 80, 255) if drowsy_count > 0 else (0, 255, 120), 2, cv2.LINE_AA)
    
    cv2.putText(frame, "Bocejos:", (w - sidebar_w + int(15 * scale), header_h + int(85 * scale)), font, font_s_sidebar_row, (180, 180, 180), 1, cv2.LINE_AA)
    cv2.putText(frame, f"{yawn_count}", (w - int(35 * scale), header_h + int(85 * scale)), font, font_s_sidebar_row + 0.05, (0, 200, 255) if yawn_count > 0 else (0, 255, 120), 2, cv2.LINE_AA)

    cv2.putText(frame, "Distracoes:", (w - sidebar_w + int(15 * scale), header_h + int(115 * scale)), font, font_s_sidebar_row, (180, 180, 180), 1, cv2.LINE_AA)
    cv2.putText(frame, f"{distracted_count}", (w - int(35 * scale), header_h + int(115 * scale)), font, font_s_sidebar_row + 0.05, (0, 165, 255) if distracted_count > 0 else (0, 255, 120), 2, cv2.LINE_AA)

    cv2.putText(frame, "Status:", (w - sidebar_w + int(15 * scale), header_h + int(150 * scale)), font, font_s_sidebar_row - 0.05, (180, 180, 180), 1, cv2.LINE_AA)
    if drowsy_alert:
        status_text = "PERIGO!"
        status_color = (0, 0, 255)
    elif distracted_alert:
        status_text = "DISTRACAO!"
        status_color = (0, 165, 255)
    elif yawn_alert:
        status_text = "FADIGA!"
        status_color = (0, 150, 255)
    else:
        status_text = "ATENTO"
        status_color = (0, 255, 120)
    cv2.putText(frame, status_text, (w - sidebar_w + int(70 * scale), header_h + int(151 * scale)), font, font_s_sidebar_row + 0.05, status_color, 2, cv2.LINE_AA)
    
    # 4. Head Pose Visual Target Tracker (Canto Superior Esquerdo, abaixo do header)
    cx = int(70 * scale)
    cy = int(160 * scale)
    r_max = int(32 * scale)
    
    # Bolinha indicator coordinates
    px = cx - int(yaw * r_max * 2.0)
    py = cy + int(pitch * r_max * 2.0)
    
    # Keep indicator within tracker circle boundaries
    dist_indicator = np.sqrt((px - cx)**2 + (py - cy)**2)
    if dist_indicator > r_max:
        angle = np.arctan2(py - cy, px - cx)
        px = cx + int(r_max * np.cos(angle))
        py = cy + int(r_max * np.sin(angle))
        
    is_out_pose = abs(yaw) > YAW_THRESHOLD or pitch > PITCH_DOWN_THRESHOLD or pitch < PITCH_UP_THRESHOLD
    blink_state = int(time.time() * 5) % 2 == 0
    
    if distracted_alert:
        color_tracker = (0, 0, 255) if blink_state else (80, 80, 255)
        color_dot = (0, 0, 255) if blink_state else (255, 0, 255)
    elif is_out_pose:
        color_tracker = (0, 165, 255) if blink_state else (40, 100, 200)
        color_dot = (0, 165, 255)
    else:
        color_tracker = (120, 120, 120)
        color_dot = (0, 255, 120)
        
    # Draw transparent backing card for Tracker
    overlay_tracker = frame.copy()
    cv2.rectangle(overlay_tracker, (int(10 * scale), int(100 * scale)), (int(220 * scale), int(210 * scale)), (20, 20, 24), -1)
    cv2.rectangle(overlay_tracker, (int(10 * scale), int(100 * scale)), (int(220 * scale), int(210 * scale)), (50, 50, 50), 1)
    cv2.addWeighted(overlay_tracker, 0.6, frame, 0.4, 0, frame)
    
    # Draw tracker circular boundaries and crosshair
    cv2.circle(frame, (cx, cy), r_max, color_tracker, 1, cv2.LINE_AA)
    cv2.circle(frame, (cx, cy), int(r_max * 0.6), (45, 45, 50), 1, cv2.LINE_AA) # inner safety boundary
    cv2.line(frame, (cx - r_max, cy), (cx + r_max, cy), (45, 45, 50), 1)
    cv2.line(frame, (cx, cy - r_max), (cx, cy + r_max), (45, 45, 50), 1)
    
    # Draw head pose dot
    cv2.circle(frame, (px, py), int(4 * scale) if scale > 0.5 else 3, color_dot, -1, cv2.LINE_AA)
    
    # Labels
    yaw_col = (0, 255, 120) if abs(yaw) <= YAW_THRESHOLD else (80, 80, 255)
    pitch_col = (0, 255, 120) if (PITCH_UP_THRESHOLD <= pitch <= PITCH_DOWN_THRESHOLD) else (80, 80, 255)
    cv2.putText(frame, "TRACKER CABECA", (int(20 * scale), int(118 * scale)), font, 0.38 * scale, (0, 180, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, f"YAW: {yaw:+.2f}", (cx + r_max + int(10 * scale), cy - int(6 * scale)), font, 0.38 * scale, yaw_col, 1, cv2.LINE_AA)
    cv2.putText(frame, f"PIT: {pitch:+.2f}", (cx + r_max + int(10 * scale), cy + int(12 * scale)), font, 0.38 * scale, pitch_col, 1, cv2.LINE_AA)

    # 5. Big Overlay Alarms for Drowsiness, Yawn, or Distraction
    alert_bar_h = int(70 * scale)
    if drowsy_alert:
        overlay_bottom = frame.copy()
        cv2.rectangle(overlay_bottom, (0, h - alert_bar_h), (w, h), (0, 0, 220), -1)
        cv2.addWeighted(overlay_bottom, 0.4, frame, 0.6, 0, frame)
        cv2.putText(frame, "ALERTA DE SONOLENCIA! FACA UMA PAUSA!", (int(20 * scale), h - int(25 * scale)), font, 0.65 * scale, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, f"{elapsed_drowsy:.1f}s", (w - int(80 * scale), h - int(25 * scale)), font, 0.65 * scale, (255, 255, 255), 2, cv2.LINE_AA)
        
    elif distracted_alert:
        overlay_bottom = frame.copy()
        cv2.rectangle(overlay_bottom, (0, h - alert_bar_h), (w, h), (0, 100, 255), -1)
        cv2.addWeighted(overlay_bottom, 0.45, frame, 0.55, 0, frame)
        cv2.putText(frame, "DISTRACAO! OLHE PARA A ESTRADA!", (int(20 * scale), h - int(25 * scale)), font, 0.6 * scale, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, f"{elapsed_distracted:.1f}s", (w - int(80 * scale), h - int(25 * scale)), font, 0.65 * scale, (255, 255, 255), 2, cv2.LINE_AA)
        
    elif yawn_alert:
        overlay_bottom = frame.copy()
        cv2.rectangle(overlay_bottom, (0, h - alert_bar_h), (w, h), (0, 100, 255), -1)
        cv2.addWeighted(overlay_bottom, 0.4, frame, 0.6, 0, frame)
        cv2.putText(frame, "BOCEJO DETECTADO - FADIGA ACUMULADA!", (int(20 * scale), h - int(25 * scale)), font, 0.6 * scale, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, f"{elapsed_yawn:.1f}s", (w - int(80 * scale), h - int(25 * scale)), font, 0.65 * scale, (255, 255, 255), 2, cv2.LINE_AA)
        
    else:
        cv2.putText(frame, "Pressione 'q' para sair e salvar relatorio", (int(15 * scale), h - int(15 * scale)), font, 0.45 * scale, (160, 160, 160), 1, cv2.LINE_AA)

def main():
    init_csv()
    
    # Inicia o servidor web Flask em segundo plano na porta 55800
    web_thread = threading.Thread(target=run_flask_server, daemon=True)
    web_thread.start()
    
    # Initialize Camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Erro: Nao foi possivel abrir a webcam.")
        print("Dica: Verifique se sua webcam esta conectada ou se o OpenCV tem permissao para usa-la.")
        return

    time.sleep(1.0)
    
    # Configure the window to be FULLY RESPONSIVE and RESIZABLE
    window_name = "Sistema de Deteccao de Sonolencia"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    
    # State tracking variables
    drowsy_start_time = None
    yawn_start_time = None
    distracted_start_time = None
    
    is_drowsy_active = False
    is_yawn_active = False
    is_distracted_active = False
    
    min_ear_during_alert = 1.0
    max_mar_during_alert = 0.0
    max_dist_during_alert = 0.0
    
    drowsy_count = 0
    yawn_count = 0
    distracted_count = 0
    
    print("\n-------------------------------------------------------------")
    print("Iniciando monitoramento. Olhe para a webcam.")
    print("Dashboard Web ativo em: http://localhost:55800")
    print("A janela de video agora e totalmente RESPONSIVA (redimensione como desejar!).")
    print("Pressione 'q' na janela de video para encerrar e ver o relatorio.")
    print("-------------------------------------------------------------\n")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Erro ao ler frame da webcam.")
            break
        
        frame = cv2.flip(frame, 1)
        height, width, _ = frame.shape
        
        # Convert BGR frame to RGB and wrap inside MediaPipe Image format
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        
        # Run detection
        detection_result = detector.detect(mp_image)
        
        current_time = time.time()
        
        # Get active window dimensions for responsive UI & crystal clear drawing
        try:
            rect = cv2.getWindowImageRect(window_name)
            if rect and rect[2] > 0 and rect[3] > 0:
                win_w, win_h = rect[2], rect[3]
            else:
                win_w, win_h = width, height
        except Exception:
            win_w, win_h = width, height
            
        # Resize frame to current window size for drawing
        display_frame = cv2.resize(frame, (win_w, win_h))
        scale = win_w / 640.0
        
        ear = 0.35  
        mar = 0.15  
        yaw = 0.0
        pitch = 0.0
        
        elapsed_drowsy = 0.0
        elapsed_yawn = 0.0
        elapsed_distracted = 0.0
        
        if detection_result.face_landmarks:
            for landmarks in detection_result.face_landmarks:
                
                # Get EAR and MAR calculated based on original camera frame to maintain strict precision
                ear = get_ear(landmarks, width, height)
                mar = get_mar(landmarks, width, height)
                yaw = get_head_yaw(landmarks)
                pitch = get_head_pitch(landmarks)
                
                # Draw precise contours on the responsively-scaled display frame
                draw_contours(display_frame, landmarks, win_w, win_h, [33, 160, 158, 133, 153, 144, 33], (255, 230, 0)) # Left eye
                draw_contours(display_frame, landmarks, win_w, win_h, [362, 385, 387, 263, 373, 380, 362], (255, 230, 0)) # Right eye
                draw_contours(display_frame, landmarks, win_w, win_h, [78, 81, 82, 13, 308, 311, 312, 14, 78], (230, 100, 255)) # Mouth
                
                # Drowsiness detection state machine
                if ear < EAR_THRESHOLD:
                    if drowsy_start_time is None:
                        drowsy_start_time = current_time
                        min_ear_during_alert = ear
                    else:
                        elapsed_drowsy = current_time - drowsy_start_time
                        min_ear_during_alert = min(min_ear_during_alert, ear)
                        
                        if elapsed_drowsy >= ALERT_DURATION:
                            is_drowsy_active = True
                            sound_manager.play_drowsy()
                else:
                    if drowsy_start_time is not None:
                        duration = current_time - drowsy_start_time
                        if is_drowsy_active:
                            log_event("DROWSINESS", duration, min_ear_during_alert)
                            drowsy_count += 1
                            sound_manager.stop_drowsy()
                            is_drowsy_active = False
                        drowsy_start_time = None
                        min_ear_during_alert = 1.0
                
                # Yawn detection state machine
                if mar > MAR_THRESHOLD:
                    if yawn_start_time is None:
                        yawn_start_time = current_time
                        max_mar_during_alert = mar
                    else:
                        elapsed_yawn = current_time - yawn_start_time
                        max_mar_during_alert = max(max_mar_during_alert, mar)
                        
                        if elapsed_yawn >= ALERT_DURATION:
                            is_yawn_active = True
                            sound_manager.play_yawn()
                else:
                    if yawn_start_time is not None:
                        duration = current_time - yawn_start_time
                        if is_yawn_active:
                            log_event("YAWN", duration, max_mar_during_alert)
                            yawn_count += 1
                            sound_manager.stop_yawn()
                            is_yawn_active = False
                        yawn_start_time = None
                        max_mar_during_alert = 0.0

                # Distraction detection state machine (Yaw & Pitch)
                is_out_pose = abs(yaw) > YAW_THRESHOLD or pitch > PITCH_DOWN_THRESHOLD or pitch < PITCH_UP_THRESHOLD
                if is_out_pose:
                    if distracted_start_time is None:
                        distracted_start_time = current_time
                        max_dist_during_alert = max(abs(yaw), abs(pitch))
                    else:
                        elapsed_distracted = current_time - distracted_start_time
                        max_dist_during_alert = max(max_dist_during_alert, abs(yaw), abs(pitch))
                        
                        if elapsed_distracted >= ALERT_DURATION:
                            is_distracted_active = True
                            sound_manager.play_distraction()
                else:
                    if distracted_start_time is not None:
                        duration = current_time - distracted_start_time
                        if is_distracted_active:
                            log_event("DISTRACTION", duration, max_dist_during_alert)
                            distracted_count += 1
                            sound_manager.stop_distraction()
                            is_distracted_active = False
                        distracted_start_time = None
                        max_dist_during_alert = 0.0
        else:
            # Face not detected, reset timers safely
            if drowsy_start_time is not None and is_drowsy_active:
                duration = current_time - drowsy_start_time
                log_event("DROWSINESS", duration, min_ear_during_alert)
                drowsy_count += 1
            if yawn_start_time is not None and is_yawn_active:
                duration = current_time - yawn_start_time
                log_event("YAWN", duration, max_mar_during_alert)
                yawn_count += 1
            if distracted_start_time is not None and is_distracted_active:
                duration = current_time - distracted_start_time
                log_event("DISTRACTION", duration, max_dist_during_alert)
                distracted_count += 1
                
            drowsy_start_time = None
            yawn_start_time = None
            distracted_start_time = None
            is_drowsy_active = False
            is_yawn_active = False
            is_distracted_active = False
            sound_manager.cleanup()
                
            # Render a nice responsive "FACE NOT DETECTED" banner
            overlay = display_frame.copy()
            cv2.rectangle(overlay, (int(30 * scale), win_h // 2 - int(30 * scale)), (win_w - int(30 * scale), win_h // 2 + int(30 * scale)), (0, 0, 150), -1)
            cv2.addWeighted(overlay, 0.6, display_frame, 0.4, 0, display_frame)
            cv2.putText(display_frame, "ROSTO NAO DETECTADO! AJUSTE A ILUMINACAO", (win_w // 2 - int(210 * scale), win_h // 2 + int(6 * scale)), cv2.FONT_HERSHEY_SIMPLEX, 0.55 * scale, (255, 255, 255), 2, cv2.LINE_AA)
            
        # Draw HUD stats on the responsively-scaled display frame
        draw_hud(display_frame, ear, mar, yaw, pitch, is_drowsy_active, is_yawn_active, is_distracted_active, drowsy_count, yawn_count, distracted_count, elapsed_drowsy, elapsed_yawn, elapsed_distracted)
        
        # Update shared_state dict for the Flask API in real time
        shared_state.update({
            "ear": float(ear),
            "mar": float(mar),
            "yaw": float(yaw),
            "pitch": float(pitch),
            "is_drowsy": bool(is_drowsy_active),
            "is_yawn": bool(is_yawn_active),
            "is_distracted": bool(is_distracted_active),
            "drowsy_count": int(drowsy_count),
            "yawn_count": int(yawn_count),
            "distracted_count": int(distracted_count),
            "elapsed_drowsy": float(elapsed_drowsy),
            "elapsed_yawn": float(elapsed_yawn),
            "elapsed_distracted": float(elapsed_distracted),
            "face_detected": bool(detection_result.face_landmarks is not None and len(detection_result.face_landmarks) > 0),
            "status": "PERIGO!" if is_drowsy_active else ("DISTRACAO!" if is_distracted_active else ("FADIGA!" if is_yawn_active else "ATENTO"))
        })
        
        cv2.imshow(window_name, display_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            if is_drowsy_active and drowsy_start_time:
                log_event("DROWSINESS", time.time() - drowsy_start_time, min_ear_during_alert)
            if is_yawn_active and yawn_start_time:
                log_event("YAWN", time.time() - yawn_start_time, max_mar_during_alert)
            if is_distracted_active and distracted_start_time:
                log_event("DISTRACTION", time.time() - distracted_start_time, max_dist_during_alert)
            break
            
    # Clean up
    cap.release()
    cv2.destroyAllWindows()
    sound_manager.cleanup()
    print("\nMonitoramento encerrado com sucesso.")
    print("Para gerar o relatorio analitico completo, execute: python analytics.py")

if __name__ == "__main__":
    main()
