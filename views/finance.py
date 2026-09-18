from datetime import datetime
from pathlib import Path
import flet as ft

CARD_COLOR = "#1E1E22"
PRIMARY_COLOR = "#2B719E"
SUCCESS_COLOR = "#10B981"
WARNING_COLOR = "#F59E0B"
ERROR_COLOR = "#EF4444"


def safe_border(width=1, color="#2A2A32"):
    """Bordure universelle sécurisée compatible Desktop et Mobile."""
    side = ft.BorderSide(width, color)
    return ft.Border(top=side, right=side, bottom=side, left=side)


def safe_icon(name, fallback="refresh"):
    """Récupère une icône de manière sécurisée quelle que soit la version de Flet."""
    for container in (getattr(ft, "Icons", None), getattr(ft, "icons", None)):
        if container and hasattr(container, name):
            val = getattr(container, name)
            if val:
                return val
    return fallback


def safe_float(val):
    """Convertit proprement n'importe quelle chaîne financière en float (gère les €, espaces et virgules)."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = (
            str(val)
            .replace("€", "")
            .replace(" ", "")
            .replace("\xa0", "")
            .replace(",", ".")
            .strip()
        )
        return float(s) if s else 0.0
    except ValueError:
        return 0.0


def parse_date(date_str):
    """Parse de manière robuste les chaînes de dates sous différents formats usuels."""
    if not date_str:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(date_str).strip().split()[0], fmt)
        except ValueError:
            continue
    return None


class FinanceView(ft.Container):

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        self.padding = 15

        # Récupération sécurisée des paramètres de base de l'entreprise
        self.entreprise_data = getattr(self.app, "entreprise", {})
        if isinstance(self.entreprise_data, dict):
            self.date_creation = self.entreprise_data.get(
                "date_creation", datetime.now().strftime("%d/%m/%Y")
            )
            self.activite = self.entreprise_data.get("type_activite", "Services")
        else:
            self.date_creation = datetime.now().strftime("%d/%m/%Y")
            self.activite = "Services"

        self._build_interface()

    def did_mount(self):
        """Se déclenche dès l'affichage pour actualiser les données réelles."""
        self.update_dashboard()

    def _build_interface(self):
        # --- 1. BLOC CONFIGURATION ---
        self.tf_date = ft.TextField(
            label="Date création",
            value=self.date_creation,
            width=140,
            height=40,
            text_size=13,
        )
        self.dd_type = ft.Dropdown(
            label="Activité",
            options=[ft.dropdown.Option("Services"), ft.dropdown.Option("Vente")],
            value=self.activite,
            width=140,
            height=40,
            text_size=13,
        )

        config_card = ft.Container(
            content=ft.Row(
                [
                    ft.Row([self.tf_date, self.dd_type], spacing=10),
                    ft.ElevatedButton(
                        "Actualiser",
                        bgcolor=PRIMARY_COLOR,
                        color="white",
                        icon=safe_icon("REFRESH_ROUNDED", "refresh"),
                        on_click=lambda _: self.update_dashboard(),
                        height=40,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            bgcolor=CARD_COLOR,
            border=safe_border(1, "#2A2A2E"),
            border_radius=8,
            padding=10,
        )

        # --- 2. ÉTIQUETTES FINANCIÈRES ---
        self.lbl_ca_mensuel = ft.Text("0.00 €", size=15, weight=ft.FontWeight.BOLD)
        self.lbl_ca_annuel = ft.Text("0.00 €", size=15, weight=ft.FontWeight.BOLD)
        self.lbl_seuil = ft.Text("0.00 €", size=15, weight=ft.FontWeight.BOLD)
        self.lbl_reste = ft.Text("0.00 €", size=15, weight=ft.FontWeight.BOLD)

        self.lbl_urssaf_mensuel = ft.Text(
            "0.00 €", size=15, weight=ft.FontWeight.BOLD, color=ERROR_COLOR
        )
        self.lbl_urssaf_annuel = ft.Text(
            "0.00 €", size=15, weight=ft.FontWeight.BOLD, color="#DC2626"
        )

        self.lbl_bc_total = ft.Text(
            "0.00 €", size=15, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR
        )
        self.lbl_bl_total = ft.Text(
            "0.00 €", size=15, weight=ft.FontWeight.BOLD, color=WARNING_COLOR
        )
        self.lbl_charges = ft.Text(
            "0.00 €", size=15, weight=ft.FontWeight.BOLD, color="red400"
        )
        self.lbl_ca_net = ft.Text(
            "0.00 €", size=15, weight=ft.FontWeight.BOLD, color=SUCCESS_COLOR
        )

        # --- 3. PROGRESSION ---
        self.progress_bar = ft.ProgressBar(
            value=0.0, color=SUCCESS_COLOR, bgcolor="#2A2A2E", height=8
        )
        self.lbl_status = ft.Text("---", size=11, italic=True)

        progression_card = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Progression vers le plafond légal :",
                        size=11,
                        color="grey400",
                    ),
                    self.progress_bar,
                    self.lbl_status,
                ],
                spacing=4,
            ),
            bgcolor="transparent",
        )

        # --- 4. COLONNE GAUCHE (STATISTIQUES) ---
        left_column = ft.Column(
            controls=[
                ft.Row(
                    [
                        self.create_stat_card("CA Ce mois-ci", self.lbl_ca_mensuel),
                        self.create_stat_card(
                            "URSSAF à verser (Mois)", self.lbl_urssaf_mensuel
                        ),
                    ],
                    spacing=10,
                ),
                ft.Row(
                    [
                        self.create_stat_card("CA Année en cours", self.lbl_ca_annuel),
                        self.create_stat_card(
                            "URSSAF Total (Année)", self.lbl_urssaf_annuel
                        ),
                    ],
                    spacing=10,
                ),
                ft.Row(
                    [
                        self.create_stat_card("Plafond (Prorata)", self.lbl_seuil),
                        self.create_stat_card("Reste à facturer", self.lbl_reste),
                    ],
                    spacing=10,
                ),
                ft.Row(
                    [
                        self.create_stat_card(
                            "Volume Bons Commande (BC)", self.lbl_bc_total
                        ),
                        self.create_stat_card(
                            "Volume Bons Livraison (BL)", self.lbl_bl_total
                        ),
                    ],
                    spacing=10,
                ),
                ft.Row(
                    [
                        self.create_stat_card(
                            "Total Charges / Dépenses", self.lbl_charges
                        ),
                        self.create_stat_card(
                            "CA Net Réel (Déduit)", self.lbl_ca_net
                        ),
                    ],
                    spacing=10,
                ),
                ft.Container(height=5),
                progression_card,
            ],
            spacing=8,
            expand=True,
        )

        # --- 5. COLONNE DROITE (GRAPHIQUE) ---
        self.chart_container = ft.Container(
            content=ft.Text("Aucune donnée disponible", color="grey400"),
            expand=True,
            alignment=ft.Alignment(0, 0),
        )

        graph_card = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Cotisations mensuelles URSSAF prévisionnelles",
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=PRIMARY_COLOR,
                    ),
                    ft.Divider(height=1, color="#2A2A2E"),
                    self.chart_container,
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                expand=True,
            ),
            bgcolor=CARD_COLOR,
            border=safe_border(1, "#2A2A2E"),
            border_radius=12,
            padding=15,
            expand=True,
        )

        # --- 6. ASSEMBLAGE ---
        dashboard_body = ft.Row(
            controls=[
                ft.Container(content=left_column, expand=11),
                ft.Container(content=graph_card, expand=9),
            ],
            spacing=15,
            expand=True,
        )

        self.content = ft.Column(
            controls=[
                ft.Row([
                    ft.Text(
                        "Tableau de Bord Financier & URSSAF",
                        size=22,
                        weight=ft.FontWeight.BOLD,
                    )
                ]),
                config_card,
                dashboard_body,
            ],
            spacing=15,
            expand=True,
        )

    def create_stat_card(self, title, label_control):
        """Génère une micro-carte financière compacte."""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        title,
                        size=10,
                        weight=ft.FontWeight.BOLD,
                        color="#A0A0A0",
                        no_wrap=True,
                    ),
                    label_control,
                ],
                spacing=2,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=CARD_COLOR,
            border=safe_border(1, "#2A2A2E"),
            border_radius=8,
            padding=10,
            expand=True,
            height=68,
        )

    def update_dashboard(self):
        """Mise à jour dynamique garantie sans erreur d'attribut."""
        if hasattr(self.app, "load_data"):
            self.app.load_data()

        now = datetime.now()
        ca_mensuel = 0.0
        ca_annuel = 0.0
        months_ca = [0.0] * 12

        factures_list = getattr(self.app, "factures", [])
        factures_valides = [
            f
            for f in factures_list
            if str(f.get("statut", "")).lower()
            in [
                "payée",
                "validée",
                "encaissée",
                "payee",
                "encaissee",
                "payé",
                "valide",
            ]
        ]

        for f in factures_valides:
            montant = safe_float(
                f.get(
                    "total_ttc",
                    f.get(
                        "montant_ttc", f.get("total_ht", f.get("montant_ht", 0))
                    ),
                )
            )
            d_str = f.get("date_paiement", f.get("date_creation", ""))
            dt = parse_date(d_str)

            if dt and dt.year == now.year:
                ca_annuel += montant
                months_ca[dt.month - 1] += montant
                if dt.month == now.month:
                    ca_mensuel += montant
            elif not dt:
                ca_annuel += montant

        is_vente = self.dd_type.value == "Vente"
        taux_urssaf = 0.123 if is_vente else 0.212
        plafond_base = 188700.0 if is_vente else 77700.0

        plafond = plafond_base
        try:
            date_crea = parse_date(self.tf_date.value)
            if date_crea and date_crea.year == now.year:
                jours_restants = (datetime(now.year, 12, 31) - date_crea).days + 1
                jours_annee = (
                    366
                    if (
                        now.year % 4 == 0
                        and (now.year % 100 != 0 or now.year % 400 == 0)
                    )
                    else 365
                )
                plafond = (plafond_base * jours_restants) / jours_annee
        except Exception:
            pass

        urssaf_mensuel = ca_mensuel * taux_urssaf
        urssaf_annuel = ca_annuel * taux_urssaf
        reste_a_facturer = max(0.0, plafond - ca_annuel)

        total_bc = sum(
            safe_float(b.get("total_ttc", b.get("montant_ttc", 0)))
            for b in getattr(self.app, "bons_commande", [])
        )
        total_bl = sum(
            safe_float(l.get("total_ttc", l.get("montant_ttc", 0)))
            for l in getattr(self.app, "bons_livraison", [])
        )

        total_charges = sum(
            safe_float(c.get("montant", 0))
            for c in getattr(self.app, "charges", [])
        )
        ca_net = ca_annuel - urssaf_annuel - total_charges

        self.lbl_ca_mensuel.value = f"{ca_mensuel:,.2f} €".replace(",", " ")
        self.lbl_ca_annuel.value = f"{ca_annuel:,.2f} €".replace(",", " ")
        self.lbl_seuil.value = f"{plafond:,.2f} €".replace(",", " ")
        self.lbl_reste.value = f"{reste_a_facturer:,.2f} €".replace(",", " ")
        self.lbl_urssaf_mensuel.value = f"{urssaf_mensuel:,.2f} €".replace(",", " ")
        self.lbl_urssaf_annuel.value = f"{urssaf_annuel:,.2f} €".replace(",", " ")
        self.lbl_bc_total.value = f"{total_bc:,.2f} €".replace(",", " ")
        self.lbl_bl_total.value = f"{total_bl:,.2f} €".replace(",", " ")
        self.lbl_charges.value = f"{total_charges:,.2f} €".replace(",", " ")
        self.lbl_ca_net.value = f"{ca_net:,.2f} €".replace(",", " ")

        pct_progression = min(1.0, ca_annuel / plafond) if plafond > 0 else 0.0
        self.progress_bar.value = pct_progression
        self.lbl_status.value = (
            f"{pct_progression * 100:.1f}% du plafond légal atteint"
            f" ({reste_a_facturer:,.2f} € disponibles)"
        )

        # --- CONSTRUCTION DU GRAPHIQUE CORRIGÉ ---
        months_labels = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
        max_tax = max([m * taux_urssaf for m in months_ca] + [100.0])
        max_height = 140.0

        chart_bars = []
        for i in range(12):
            monthly_tax = months_ca[i] * taux_urssaf
            height_ratio = monthly_tax / max_tax if max_tax > 0 else 0
            bar_h = max(4.0, height_ratio * max_height)
            bar_color = PRIMARY_COLOR if monthly_tax > 0 else "#2A2A32"

            chart_bars.append(
                ft.Column(
                    controls=[
                        ft.Container(
                            width=14,
                            height=bar_h,
                            bgcolor=bar_color,
                            border_radius=3,
                            tooltip=f"{monthly_tax:,.2f} €".replace(",", " "),
                        ),
                        ft.Text(months_labels[i], size=10, color="grey400"),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.END,
                    spacing=4,
                )
            )

        self.chart_container.content = ft.Row(
            controls=chart_bars,
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
            vertical_alignment=ft.CrossAxisAlignment.END,
            expand=True,
        )

        if self.page:
            self.update()
```[cite: 20]
