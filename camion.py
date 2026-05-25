#!/opt/copilot-env/bin/python3
from ultralytics import YOLO
import cv2, json, socket, time
import warnings, logging, os

os.environ["TORCH_CPP_LOG_LEVEL"] = "ERROR"
warnings.filterwarnings("ignore")
logging.getLogger("ultralytics").setLevel(logging.ERROR)

# ─── Configuration ─────────────────────────────────────────────
HOTE          = "10.0.0.2"
PORT_UDP      = 5000
PORT_TCP      = 5001
PORT_COMMANDE = 5002        # réception commandes mode adaptatif
MODELE        = "/home/wifi/copilot/yolov8n.pt"
VIDEO         = "/home/wifi/copilot/video.mp4"
MODE          = "adaptatif" # "json" | "video" | "adaptatif"
MODE_INITIAL  = "video"     # mode de départ si adaptatif
JPEG_QUALITE  = 80
SORTIE_VIDEO  = "/home/wifi/copilot/analysis/results/video_annotee.mp4"
# ───────────────────────────────────────────────────────────────

CLASSES_DANGER = {"car","truck","bus","motorcycle","person","bicycle"}
NIVEAUX        = ["NONE","LOW","MEDIUM","HIGH"]


def calculer_danger(bbox, classe, frame_w, frame_h):
    x1, y1, x2, y2 = bbox
    ratio_surface   = ((x2-x1)*(y2-y1)) / (frame_w*frame_h)
    ratio_centre_x  = ((x1+x2)/2) / frame_w
    en_trajectoire  = 0.25 < ratio_centre_x < 0.75
    classe_danger   = classe in CLASSES_DANGER
    if classe_danger and en_trajectoire and ratio_surface > 0.08:
        niveau = "HIGH"
    elif classe_danger and (en_trajectoire or ratio_surface > 0.04):
        niveau = "MEDIUM"
    elif classe_danger:
        niveau = "LOW"
    else:
        niveau = "NONE"
    return {
        "niveau"        : niveau,
        "ratio_surface" : round(ratio_surface, 4),
        "en_trajectoire": en_trajectoire,
        "centre_x"      : round(ratio_centre_x, 3)
    }


def danger_max(objets):
    return max(
        (o["danger"]["niveau"] for o in objets),
        key=lambda n: NIVEAUX.index(n),
        default="NONE"
    )


def annoter_frame(frame, objets, danger_global, mode_affiche):
    couleurs = {
        "HIGH"  : (0, 0, 255),
        "MEDIUM": (0, 165, 255),
        "LOW"   : (0, 255, 0),
        "NONE"  : (255, 255, 255)
    }
    for obj in objets:
        x1, y1, x2, y2 = [int(v) for v in obj["bbox"]]
        c = couleurs.get(obj["danger"]["niveau"], (255,255,255))
        cv2.rectangle(frame, (x1,y1), (x2,y2), c, 2)
        cv2.putText(frame,
            f"{obj['classe']} {obj['confiance']:.2f} [{obj['danger']['niveau']}]",
            (x1, y1-8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, c, 1)
    cb = couleurs.get(danger_global, (255,255,255))
    cv2.rectangle(frame, (0,0), (frame.shape[1],30), cb, -1)
    cv2.putText(frame, f"DANGER:{danger_global} | MODE:{mode_affiche}",
                (10,22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 2)
    return frame


def lire_commande(sock_cmd, mode_actuel):
    """Lit une commande de mode (non bloquant)."""
    try:
        data, _ = sock_cmd.recvfrom(1024)
        cmd = json.loads(data.decode())
        nouveau = cmd.get("mode", mode_actuel)
        if nouveau != mode_actuel:
            print(f"[CAMION] Mode reçu : {mode_actuel} → {nouveau}")
        return nouveau
    except socket.timeout:
        return mode_actuel


def main():
    # Socket UDP envoi données
    sock_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Socket TCP pour mode vidéo fixe
    sock_tcp = None
    if MODE == "video":
        print(f"[CAMION] Connexion TCP vers {HOTE}:{PORT_TCP}...")
        sock_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock_tcp.connect((HOTE, PORT_TCP))
        print("[CAMION] Connecte en TCP")

    # Socket réception commandes (mode adaptatif)
    sock_cmd = None
    if MODE == "adaptatif":
        sock_cmd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_cmd.bind(("10.0.0.1", PORT_COMMANDE))
        sock_cmd.settimeout(0.01)  # non bloquant
        print(f"[CAMION] Ecoute commandes sur port {PORT_COMMANDE}")

    model   = YOLO(MODELE)
    cap     = cv2.VideoCapture(VIDEO)

    if not cap.isOpened():
        print(f"[ERREUR] Impossible d'ouvrir : {VIDEO}")
        return

    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fps     = cap.get(cv2.CAP_PROP_FPS) or 30

    # Sauvegarde vidéo annotée
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(SORTIE_VIDEO, fourcc, fps, (frame_w, frame_h))

    # Mode courant
    mode_courant = MODE_INITIAL if MODE == "adaptatif" else MODE
    print(f"[CAMION] {frame_w}x{frame_h} | mode:{MODE} | "
          f"mode_initial:{mode_courant}")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[CAMION] Fin de la video")
                break

            # Lire commande de mode si adaptatif
            if MODE == "adaptatif" and sock_cmd:
                mode_courant = lire_commande(sock_cmd, mode_courant)

            # Inférence YOLO
            resultats = model(frame, verbose=False)
            objets = []
            for box in resultats[0].boxes:
                cls  = int(box.cls)
                bbox = box.xyxy.tolist()[0]
                objets.append({
                    "classe"    : model.names[cls],
                    "confiance" : round(float(box.conf), 3),
                    "bbox"      : bbox,
                    "danger"    : calculer_danger(bbox, model.names[cls],
                                                  frame_w, frame_h)
                })

            dg = danger_max(objets)
            fa = annoter_frame(frame.copy(), objets, dg, mode_courant)
            writer.write(fa)

            # Envoi selon le mode courant
            if mode_courant == "video":
                _, buffer = cv2.imencode('.jpg', fa,
                                [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITE])
                donnees = buffer.tobytes()
                taille  = len(donnees).to_bytes(4, byteorder='big')
                # En adaptatif, on passe par UDP même pour la vidéo
                # (limité à 65507 octets — réduire la qualité si nécessaire)
                if len(donnees) + 4 <= 65507:
                    sock_udp.sendto(taille + donnees, (HOTE, PORT_UDP))
                else:
                    # Frame trop grande → forcer JSON pour cette frame
                    payload = {
                        "timestamp"     : time.time(),
                        "mode"          : "json",
                        "danger_global" : dg,
                        "objets"        : objets
                    }
                    sock_udp.sendto(json.dumps(payload).encode(),
                                    (HOTE, PORT_UDP))

            elif mode_courant == "json":
                payload = {
                    "timestamp"     : time.time(),
                    "mode"          : "json",
                    "danger_global" : dg,
                    "objets"        : objets
                }
                sock_udp.sendto(json.dumps(payload).encode(), (HOTE, PORT_UDP))

            elif mode_courant == "minimal":
                payload = {
                    "timestamp"     : time.time(),
                    "mode"          : "minimal",
                    "danger_global" : dg
                }
                sock_udp.sendto(json.dumps(payload).encode(), (HOTE, PORT_UDP))

            time.sleep(0.033)

    except (KeyboardInterrupt, BrokenPipeError):
        print("\n[CAMION] Arret")
    finally:
        cap.release()
        writer.release()
        sock_udp.close()
        if sock_tcp:
            sock_tcp.close()
        if sock_cmd:
            sock_cmd.close()
        print(f"[CAMION] Video annotee : {SORTIE_VIDEO}")
        print("[CAMION] Termine")


if __name__ == '__main__':
    main()
