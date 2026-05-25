import sys
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QComboBox, QPushButton, QFrame)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

class SimulateurReseau(QWidget):
    def __init__(self):
        super().__init__()
        
        # Base de données structurée par Format -> Paramètre -> Valeur
        self.data = {
            "JSON": {
                "latence": {
                    "Normale": 11.98995708,
                    "50ms": 87.49212017,
                    "200ms": 222.2122318
                },
                "perte": {
                    "Normale": 3.016309013,
                    "10%": 2.997177799
                },
                "bp": {
                    "Normale": 30.58501288,
                    "1 Mbps": 24.77512446,
                    "500 kbps": 39.94096996,
                    "200 kbps": 38.56353648
                }
            },
            "VIDEO": {
                "latence": {
                    "Normale": 111.7203605,
                    "50ms": 393.6590386,
                    "200ms": 828.8738455
                },
                "perte": {
                    "Normale": 0.0,
                    "10%": 0.0
                },
                "bp": {
                    "Normale": "3066,83334763949",
                    "1 Mbps": 851.7298369,
                    "500 kbps": 476.2472961,
                    "200 kbps": "N/A" 
                }
            }
        }
        
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Simulateur Réseau - JSON & VIDEO")
        self.resize(650, 400)
        
        layout_principal = QVBoxLayout()
        layout_principal.setSpacing(15)

        # Titre
        titre = QLabel("Sélection des Paramètres de Simulation")
        titre.setFont(QFont('Arial', 16, QFont.Bold))
        titre.setAlignment(Qt.AlignCenter)
        layout_principal.addWidget(titre)

        ligne = QFrame()
        ligne.setFrameShape(QFrame.HLine)
        ligne.setFrameShadow(QFrame.Sunken)
        layout_principal.addWidget(ligne)

        # Layout des ComboBoxes
        layout_combos = QHBoxLayout()

        # 1. ComboBox Format 
        layout_format = QVBoxLayout()
        layout_format.addWidget(QLabel("Format :"))
        self.combo_format = QComboBox()
        self.combo_format.addItems(["JSON", "VIDEO"])
        layout_format.addWidget(self.combo_format)
        layout_combos.addLayout(layout_format)

        # 2. ComboBox Latence
        layout_lat = QVBoxLayout()
        layout_lat.addWidget(QLabel("Latence :"))
        self.combo_latence = QComboBox()
        self.combo_latence.addItems(["Normale", "50ms", "200ms"])
        layout_lat.addWidget(self.combo_latence)
        layout_combos.addLayout(layout_lat)

        # 3. ComboBox Perte
        layout_perte = QVBoxLayout()
        layout_perte.addWidget(QLabel("Perte de paquets :"))
        self.combo_perte = QComboBox()
        self.combo_perte.addItems(["Normale", "10%"])
        layout_perte.addWidget(self.combo_perte)
        layout_combos.addLayout(layout_perte)

        # 4. ComboBox Bande passante
        layout_bp = QVBoxLayout()
        layout_bp.addWidget(QLabel("Bande passante :"))
        self.combo_bp = QComboBox()
        self.combo_bp.addItems(["Normale", "1 Mbps", "500 kbps", "200 kbps"])
        layout_bp.addWidget(self.combo_bp)
        layout_combos.addLayout(layout_bp)
        
        layout_principal.addLayout(layout_combos)

        # Bouton
        self.bouton_valider = QPushButton("Valider les paramètres")
        self.bouton_valider.setFont(QFont('Arial', 10, QFont.Bold))
        self.bouton_valider.setMinimumHeight(40)
        self.bouton_valider.clicked.connect(self.afficher_resultats)
        layout_principal.addWidget(self.bouton_valider)

        # Affichage Résultats
        self.label_resultat = QLabel("Veuillez sélectionner vos paramètres et cliquer sur Valider.")
        self.label_resultat.setFont(QFont('Arial', 11))
        self.label_resultat.setStyleSheet("background-color: #f8f9fa; border: 1px solid #ced4da; padding: 15px; border-radius: 5px;")
        self.label_resultat.setWordWrap(True)
        self.label_resultat.setAlignment(Qt.AlignCenter)
        layout_principal.addWidget(self.label_resultat)

        self.setLayout(layout_principal)

    def formater_nombre(self, valeur):
        """ Transforme un float (ex: 11.98) en chaîne française (11,98) pour l'affichage """
        if isinstance(valeur, (float, int)):
            return str(valeur).replace('.', ',')
        return str(valeur)

    def afficher_resultats(self):
        # Récupération des choix
        fmt = self.combo_format.currentText()
        lat = self.combo_latence.currentText()
        perte = self.combo_perte.currentText()
        bp = self.combo_bp.currentText()
        
        #Si VIDEO et BP = 200 kbps => Échec immédiat
        if fmt == "VIDEO" and bp == "200 kbps":
            self.label_resultat.setAlignment(Qt.AlignCenter)
            self.label_resultat.setText(
                "<span style='color:#d9534f; font-size:16px; font-weight:bold;'>"
                "inutilisable, la bande passante est trop faible."
                "</span>"
            )
            return
            
        # Récupération des valeurs brutes dans le dictionnaire
        val_lat = self.data[fmt]["latence"][lat]
        val_perte = self.data[fmt]["perte"][perte]
        val_bp = self.data[fmt]["bp"][bp]
        
        if fmt == "VIDEO" and perte == "10%":
            val_lat = val_lat * 2
            avertissement_latence = ""
        else:
            avertissement_latence = ""
            
        # Formatage avec la virgule
        str_lat = self.formater_nombre(val_lat)
        str_perte = self.formater_nombre(val_perte)
        str_bp = self.formater_nombre(val_bp)
        
        # Construction de l'affichage HTML
        texte_resultat = (
            f"<h3 style='margin-top:0;'>Résultats de la simulation ({fmt}) :</h3>"
            f"<ul style='margin-bottom:0;'>"
            f"<li><b>Latence mesurée :</b> {str_lat} ms {avertissement_latence}</li>"
            f"<li><b>Nombre d'objets :</b> {str_perte}</li>"
            f"<li><b>Débit :</b> {str_bp} kbps</li>"
            f"</ul>"
        )
        
        self.label_resultat.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.label_resultat.setText(texte_resultat)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    fenetre = SimulateurReseau()
    fenetre.show()
    sys.exit(app.exec_())
