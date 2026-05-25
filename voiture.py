#!/opt/copilot-env/bin/python3
import socket, json, time, csv, os
import numpy as np
import cv2

# ─── Configuration ─────────────────────────────────────────────
HOTE                  = "10.0.0.2"
PORT_UDP              = 5000
PORT_TCP              = 5001
PORT_COMMANDE         = 5002        # commandes mode adaptatif → camion
HOTE_CAMION           = "10.0.0.1"
MODE                  = "adaptatif" # "json" | "video" | "adaptatif"
LOG_CSV               = "/home/wifi/copilot/analysis/results/mesures.csv"
LOG_HANDOVER          = "/home/wifi/copilot/analysis/results/handover.csv"
INTERVALLE_DEBIT      = 5.0

# ─── Seuils mode adaptatif ─────────────────────────────────────
SEUIL_LATENCE_JSON    = 80    # ms  → passer en json si latence > seuil
SEUIL_LATENCE_MINIMAL = 200   # ms  → passer en minimal si latence > seuil
SEUIL_PERTE           = 0.15  # 15% → passer en minimal si perte > seuil
FENETRE_MESURE        = 10    # nb frames pour calculer latence moyenne
# ───────────────────────────────────────────────────────────────

COULEURS = {
    "HIGH"  : "\033[91m",
    "MEDIUM": "\033[93m",
    "LOW"   : "\033[92m",
    "NONE"  : "\033[97m",
    "RESET" : "\033[0m"
}


def initialiser_log():
    os.makedirs(os.path.dirname(LOG_CSV), exist_ok=True)
    with open(LOG_CSV, 'w', newline='') as f:
        csv.writer(f).writerow([
            "timestamp", "latence_ms", "nb_objets",
            "danger_global", "debit_kbps", "mode_actif"
        ])
    print(f"[VOITURE] CSV initialise : {LOG_CSV}")


def initialiser_log_handover():
    os.makedirs(os.path.dirname(LOG_HANDOVER), exist_ok=True)
    with open(LOG_HANDOVER, 'w', newline='') as f:
        csv.writer(f).writerow([
            "timestamp", "duree_interruption_s", "paquets_perdus_estimes"
        ])


def logger_mesure(timestamp_envoi, nb_objets, danger, debit_kbps=0.0, mode="json"):
    latence = round((time.time() - timestamp_envoi) * 1000, 2)
    with open(LOG_CSV, 'a', newline='') as f:
        csv.writer(f).writerow([
            time.strftime("%H:%M:%S"), latence,
            nb_objets, danger, round(debit_kbps, 2), mode
        ])
    return latence


def logger_interruption(duree_s):
    paquets_perdus = round(duree_s * 30)
    with open(LOG_HANDOVER, 'a', newline='') as f:
        csv.writer(f).writerow([
            time.strftime("%H:%M:%S"), duree_s, paquets_perdus
        ])
    print(f"[HANDOVER] {duree_s}s | ~{paquets_perdus} paquets perdus")


def afficher_decision(danger, nb_objets, latence_ms, debit_kbps, mode):
    c = COULEURS.get(danger, COULEURS["RESET"])
    print(f"{c}DANGER:{danger:<6} | {nb_objets} obj "
          f"| {latence_ms:.1f}ms "
          f"| {debit_kbps:.1f}kbps "
          f"| [{mode}]{COULEURS['RESET']}")


def choisir_mode(latence_moy, taux_perte):
    """
    Logique de décision du mode adaptatif.
    Retourne : 'video', 'json' ou 'minimal'
    """
    if latence_moy > SEUIL_LATENCE_MINIMAL or taux_perte > SEUIL_PERTE:
        return "minimal"
    elif latence_moy > SEUIL_LATENCE_JSON:
        return "json"
    else:
        return "video"


def envoyer_commande(sock_cmd, mode):
    """Envoie la commande de mode au camion sur port 5002."""
    commande = json.dumps({"mode": mode}).encode()
    sock_cmd.sendto(commande, (HOTE_CAMION, PORT_COMMANDE))
    print(f"[ADAPTATIF] Commande envoyée au camion : {mode}")


def recevoir_json(sock, sock_cmd=None, adaptatif=False):
    octets_recus     = 0
    t_debit          = time.time()
    debit_kbps       = 0.0
    t_dernier_paquet = time.time()
    interruption     = False
    t_interruption   = None
    mode_actuel      = "video" if adaptatif else "json"
    historique_lat   = []
    compteur_total   = 0
    compteur_recus   = 0

    while True:
        try:
            donnees, _ = sock.recvfrom(65535)
            compteur_recus += 1

            # Détection reprise après interruption
            if interruption:
                duree = round(time.time() - t_interruption, 2)
                print(f"[HANDOVER] Reprise ! Interruption : {duree}s")
                logger_interruption(duree)
                interruption = False
            t_dernier_paquet = time.time()

        except socket.timeout:
            compteur_total += 1
            delai = time.time() - t_dernier_paquet
            if delai > 1.0 and not interruption:
                interruption   = True
                t_interruption = time.time()
                print("[HANDOVER] Interruption détectée !")
            elif interruption:
                print(f"[HANDOVER] Toujours interrompu... "
                      f"{round(time.time()-t_interruption, 1)}s")
            else:
                print("[VOITURE] Timeout — pas de donnees")
            continue

        compteur_total += 1

        try:
            payload = json.loads(donnees.decode())
        except json.JSONDecodeError:
            continue

        danger    = payload.get("danger_global", "NONE")
        objets    = payload.get("objets", [])
        timestamp = payload.get("timestamp", time.time())

        # Calcul débit
        octets_recus += len(donnees)
        elapsed = time.time() - t_debit
        if elapsed >= INTERVALLE_DEBIT:
            debit_kbps   = (octets_recus * 8) / elapsed / 1000
            print(f"[DEBIT] {debit_kbps:.1f} kbps "
                  f"({octets_recus} octets en {elapsed:.1f}s)")
            octets_recus = 0
            t_debit      = time.time()

        latence = logger_mesure(timestamp, len(objets), danger,
                                debit_kbps, mode_actuel)
        afficher_decision(danger, len(objets), latence, debit_kbps, mode_actuel)

        for obj in objets:
            d = obj["danger"]
            print(f"   +- {obj['classe']:<15} "
                  f"conf:{obj['confiance']:.2f}  "
                  f"danger:{d['niveau']:<6}  "
                  f"traj:{str(d['en_trajectoire']):<5}  "
                  f"surface:{d['ratio_surface']:.3f}")
        print()

        # ── Mode adaptatif ──────────────────────────────────────
        if adaptatif and sock_cmd:
            historique_lat.append(latence)
            if len(historique_lat) > FENETRE_MESURE:
                historique_lat.pop(0)

            latence_moy  = sum(historique_lat) / len(historique_lat)
            taux_perte   = 1 - (compteur_recus / max(compteur_total, 1))
            nouveau_mode = choisir_mode(latence_moy, taux_perte)

            if nouveau_mode != mode_actuel:
                print(f"[ADAPTATIF] {mode_actuel} → {nouveau_mode} "
                      f"(lat:{latence_moy:.0f}ms | "
                      f"perte:{taux_perte:.0%})")
                mode_actuel = nouveau_mode
                envoyer_commande(sock_cmd, mode_actuel)
        # ────────────────────────────────────────────────────────


def recevoir_video(conn):
    octets_recus  = 0
    t_debit       = time.time()
    debit_kbps    = 0.0
    frames_recues = 0

    while True:
        raw_taille = b""
        while len(raw_taille) < 4:
            chunk = conn.recv(4 - len(raw_taille))
            if not chunk:
                return
            raw_taille += chunk

        taille      = int.from_bytes(raw_taille, byteorder='big')
        donnees     = b""
        t_reception = time.time()
        while len(donnees) < taille:
            chunk = conn.recv(min(4096, taille - len(donnees)))
            if not chunk:
                return
            donnees += chunk

        frames_recues += 1
        octets_recus  += taille
        elapsed = time.time() - t_debit
        if elapsed >= INTERVALLE_DEBIT:
            debit_kbps    = (octets_recus * 8) / elapsed / 1000
            print(f"[DEBIT] {debit_kbps:.1f} kbps "
                  f"({frames_recues} frames | {octets_recus} octets)")
            octets_recus  = 0
            frames_recues = 0
            t_debit       = time.time()

        latence = round((time.time() - t_reception) * 1000, 2)
        logger_mesure(t_reception, 0, "VIDEO_FRAME", debit_kbps, "video")
        print(f"[VOITURE] Frame {frames_recues} | "
              f"{taille} octets | {latence:.1f}ms | {debit_kbps:.1f}kbps")


def main():
    initialiser_log()
    initialiser_log_handover()

    # Socket de commande (mode adaptatif → camion)
    sock_cmd = None
    if MODE == "adaptatif":
        sock_cmd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print(f"[VOITURE] Mode adaptatif activé")
        print(f"[VOITURE] Seuils : JSON>{SEUIL_LATENCE_JSON}ms | "
              f"MINIMAL>{SEUIL_LATENCE_MINIMAL}ms | "
              f"PERTE>{SEUIL_PERTE:.0%}")

    if MODE in ("json", "adaptatif"):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((HOTE, PORT_UDP))
        sock.settimeout(1.0)
        print(f"[VOITURE] Ecoute UDP {HOTE}:{PORT_UDP} | mode:{MODE}\n")
        try:
            recevoir_json(sock, sock_cmd, adaptatif=(MODE == "adaptatif"))
        except KeyboardInterrupt:
            print("\n[VOITURE] Arret")
        finally:
            sock.close()
            if sock_cmd:
                sock_cmd.close()

    elif MODE == "video":
        serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serveur.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        serveur.bind(("0.0.0.0", PORT_TCP))
        serveur.listen(1)
        print(f"[VOITURE] Attente TCP 0.0.0.0:{PORT_TCP} | mode:video\n")
        conn, addr = serveur.accept()
        print(f"[VOITURE] Camion connecte depuis {addr}\n")
        try:
            recevoir_video(conn)
        except KeyboardInterrupt:
            print("\n[VOITURE] Arret")
        finally:
            conn.close()
            serveur.close()

    print(f"[VOITURE] Resultats : {LOG_CSV}")


if __name__ == '__main__':
    main()
