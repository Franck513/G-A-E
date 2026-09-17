import os
import smtplib
import sys
import threading
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import flet as ft

# Détection sécurisée d'Android
IS_ANDROID = (
    "ANDROID_STORAGE" in os.environ
    or "ANDROID_ROOT" in os.environ
    or hasattr(sys, "getandroidapilevel")
)


def get_icon(name: str):
    """Assistant universel d'icônes pour la compatibilité Android et Desktop."""
    name_upper = name.upper()
    if hasattr(ft, "Icons") and hasattr(ft.Icons, name_upper):
        return getattr(ft.Icons, name_upper)
    if hasattr(ft, "icons") and hasattr(ft.icons, name_upper):
        return getattr(ft.icons, name_upper)
    return name.lower()


class CustomTabs(ft.Column):
    """Système d'onglets personnalisé 100% compatible Android APK & Desktop."""

    def __init__(self, tabs_data, selected_index=0, accent_color="#2B719E"):
        super().__init__(expand=True, spacing=10)
        self.tabs_data = tabs_data
        self.selected_index = selected_index
        self.accent_color = accent_color

        self.buttons_row = ft.Row(spacing=5, scroll="auto")
        self.content_container = ft.Container(expand=True)

        self.controls = [self.buttons_row, self.content_container]
        self.render_tabs()

    def render_tabs(self):
        self.buttons_row.controls.clear()
        for idx, tab in enumerate(self.tabs_data):
            is_selected = idx == self.selected_index

            btn_widgets = []
            icon_val = tab.get("icon")
            if icon_val:
                icon_obj = (
                    get_icon(icon_val) if isinstance(icon_val, str) else icon_val
                )
                btn_widgets.append(
                    ft.Icon(
                        icon_obj, size=16, color="white" if is_selected else "grey400"
                    )
                )

            btn_widgets.append(
                ft.Text(
                    tab.get("label", ""),
                    size=12,
                    weight="bold" if is_selected else "normal",
                    color="white" if is_selected else "grey300",
                )
            )

            try:
                pad = ft.padding.only(left=12, top=8, right=12, bottom=8)
            except Exception:
                pad = 8

            btn = ft.Container(
                content=ft.Row(btn_widgets, spacing=6, alignment="center"),
                padding=pad,
                border_radius=8,
                bgcolor=self.accent_color if is_selected else "#111827",
                ink=True,
                on_click=lambda e, i=idx: self.select_tab(i),
            )
            self.buttons_row.controls.append(btn)

        if 0 <= self.selected_index < len(self.tabs_data):
            self.content_container.content = self.tabs_data[self.selected_index][
                "content"
            ]

    def select_tab(self, index):
        self.selected_index = index
        self.render_tabs()
        try:
            if self.page:
                self.update()
        except Exception:
            pass


class MailsView(ft.Container):

    def __init__(self, app):
        super().__init__(expand=True)
        self.app = app

        # Récupération de la couleur et du nom de l'entreprise
        self.entreprise_data = getattr(
            self.app, "entreprise", getattr(self.app, "association", {})
        )
        self.accent_color = self.entreprise_data.get("accent_color", "#2B719E")

        # Gestion des fichiers joints
        self.attachments = []
        if not IS_ANDROID:
            self.file_picker = ft.FilePicker()
            self.file_picker.on_result = self.on_attachment_picked
        else:
            self.file_picker = None

        # Indicateur de chargement pour les envois
        self.progress_ring = ft.ProgressRing(
            width=20, height=20, stroke_width=2, visible=False
        )
        self.btn_send = ft.ElevatedButton(
            "🚀 Envoyer l'email",
            icon=get_icon("SEND"),
            bgcolor=self.accent_color,
            color="white",
            height=48,
            on_click=self.envoyer_email,
        )

        # --- COMPOSANTS DE COMPOSITION ---
        self.dd_destinataires = ft.Dropdown(
            label="Groupe de destinataires",
            options=[
                ft.dropdown.Option("TOUS", "Tous les clients & contacts"),
                ft.dropdown.Option("CLIENTS", "Clients uniquement"),
                ft.dropdown.Option("PROSPECTS", "Prospects / Devis en cours"),
                ft.dropdown.Option(
                    "MANUEL", "Adresse spécifique (Saisie manuelle)"
                ),
            ],
            value="TOUS",
            col={"sm": 12, "md": 6},
        )
        self.dd_destinataires.on_change = self.on_destinataires_change

        self.input_email_manuel = ft.TextField(
            label="Email destinataire unique",
            hint_text="client@domaine.com",
            visible=False,
            col={"sm": 12, "md": 6},
        )

        self.input_sujet = ft.TextField(
            label="Sujet de l'email",
            hint_text="Ex: Relance facture / Suivi de votre commande",
            col={"sm": 12},
        )

        self.input_corps = ft.TextField(
            label="Message / Contenu de l'email",
            multiline=True,
            min_lines=8,
            max_lines=15,
            expand=True,
            hint_text="Rédigez votre message ici...",
        )

        self.list_attachments = ft.Row(spacing=10, wrap=True)

        # --- COMPOSANTS CONFIGURATION SMTP ---
        config_smtp = getattr(self.app, "config_smtp", {})
        self.input_smtp_host = ft.TextField(
            label="Serveur SMTP",
            value=config_smtp.get("host", "smtp.gmail.com"),
            col={"sm": 12, "md": 6},
        )
        self.input_smtp_port = ft.TextField(
            label="Port SMTP",
            value=str(config_smtp.get("port", 587)),
            col={"sm": 6, "md": 3},
            keyboard_type="number",
        )
        self.check_smtp_tls = ft.Checkbox(
            label="Utiliser TLS / STARTTLS", value=config_smtp.get("use_tls", True)
        )
        self.input_smtp_user = ft.TextField(
            label="Nom d'utilisateur / Email d'envoi",
            value=config_smtp.get("user", ""),
            col={"sm": 12, "md": 6},
        )
        self.input_smtp_pass = ft.TextField(
            label="Mot de passe d'application",
            password=True,
            can_reveal_password=True,
            value=config_smtp.get("password", ""),
            col={"sm": 12, "md": 6},
        )
        self.input_sender_name = ft.TextField(
            label="Nom d'expéditeur affiché",
            value=config_smtp.get(
                "sender_name", self.entreprise_data.get("nom", "Mon Entreprise")
            ),
            col={"sm": 12, "md": 6},
        )

        # Table d'historique
        self.table_historique = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Date")),
                ft.DataColumn(ft.Text("Destinataires")),
                ft.DataColumn(ft.Text("Sujet")),
                ft.DataColumn(ft.Text("Statut")),
            ],
            rows=[],
        )

        # Structure principale par Onglets
        self.content = self._build_main_view()

    def safe_update(self):
        """Mise à jour sécurisée de l'interface."""
        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def did_mount(self):
        """Enregistre le FilePicker sur Desktop et vérifie les e-mails en attente."""
        if not IS_ANDROID:
            page_obj = getattr(self.app, "page", None) or self.page
            if page_obj and self.file_picker:
                try:
                    if self.file_picker not in page_obj.overlay:
                        page_obj.overlay.append(self.file_picker)
                except Exception:
                    pass

        # Traitement automatique du mail transmis par le visualiseur PDF
        self.check_pending_email()
        self.safe_update()

    def check_pending_email(self):
        """Récupère et pré-remplit les données transmises depuis le visualiseur PDF."""
        pending = getattr(self.app, "pending_email", None) if self.app else None
        if pending and isinstance(pending, dict):
            dest = pending.get("email", "").strip()
            sujet = pending.get("sujet", "").strip()
            corps = pending.get("corps", "").strip()
            attachment = pending.get("attachment")

            if dest:
                self.dd_destinataires.value = "MANUEL"
                self.input_email_manuel.visible = True
                self.input_email_manuel.value = dest

            if sujet:
                self.input_sujet.value = sujet
            if corps:
                self.input_corps.value = corps

            if attachment:
                att_path = Path(attachment)
                if att_path.exists() and att_path not in self.attachments:
                    self.attachments.append(att_path)
                self.rafraichir_attachments_ui()

            self.app.pending_email = None
            self.safe_update()

    def will_unmount(self):
        """Nettoie le FilePicker de l'overlay."""
        if not IS_ANDROID:
            page_obj = getattr(self.app, "page", None) or self.page
            if page_obj and self.file_picker:
                try:
                    if self.file_picker in page_obj.overlay:
                        page_obj.overlay.remove(self.file_picker)
                except Exception:
                    pass

    # ============================================================
    # CONSTRUCTION DES ONGLETS
    # ============================================================

    def _build_main_view(self):
        tabs_obj = CustomTabs(
            tabs_data=[
                {
                    "label": "Composition",
                    "content": self._build_tab_composition(),
                    "icon": "EMAIL",
                },
                {
                    "label": "Modèles Entreprise",
                    "content": self._build_tab_modeles(),
                    "icon": "AUTO_MODE",
                },
                {
                    "label": "Historique d'envois",
                    "content": self._build_tab_historique(),
                    "icon": "HISTORY",
                },
                {
                    "label": "Configuration SMTP",
                    "content": self._build_tab_smtp(),
                    "icon": "SETTINGS",
                },
            ],
            selected_index=0,
            accent_color=self.accent_color,
        )
        return tabs_obj

    def _build_tab_composition(self):
        return ft.Container(
            padding=15,
            content=ft.Column(
                [
                    ft.Text(
                        "✉️ Rédiger un e-mail professionnel",
                        size=16,
                        weight="bold",
                    ),
                    ft.ResponsiveRow([
                        self.dd_destinataires,
                        self.input_email_manuel,
                    ]),
                    ft.ResponsiveRow([self.input_sujet]),
                    self.input_corps,
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                "📎 Joindre un fichier",
                                icon=get_icon("ATTACH_FILE"),
                                on_click=self.joindre_fichier_click,
                            ),
                            self.list_attachments,
                        ],
                        wrap=True,
                    ),
                    ft.Divider(color="grey800"),
                    ft.Row(
                        [self.progress_ring, self.btn_send],
                        alignment="end",
                        vertical_alignment="center",
                        spacing=10,
                    ),
                ],
                spacing=12,
                scroll="auto",
            ),
        )

    def joindre_fichier_click(self, e):
        if IS_ANDROID:
            self._show_snackbar(
                "La sélection directe de pièces jointes n'est pas activée sur cet APK"
                " Android."
            )
            return
        if self.file_picker:
            try:
                self.file_picker.pick_files(allow_multiple=True)
            except Exception as ex:
                self._show_snackbar(f"Sélecteur indisponible : {ex}", is_error=True)

    def _build_tab_modeles(self):
        return ft.Container(
            padding=15,
            content=ft.Column(
                [
                    ft.Text(
                        "⚡ Modèles de messages commercial & relances",
                        size=16,
                        weight="bold",
                    ),
                    ft.Text(
                        "Cliquez sur un modèle pour pré-remplir le sujet et le"
                        " message.",
                        size=12,
                        italic=True,
                        color="grey400",
                    ),
                    ft.ResponsiveRow(
                        [
                            ft.Container(
                                col={"sm": 12, "md": 4},
                                padding=12,
                                bgcolor="#1e293b",
                                border_radius=8,
                                content=ft.Column(
                                    [
                                        ft.Text(
                                            "💳 Relance Facture Impayée",
                                            weight="bold",
                                            size=14,
                                            color="#93C5FD",
                                        ),
                                        ft.Text(
                                            "Rappelle à un client qu'une facture"
                                            " est en attente de paiement.",
                                            size=12,
                                            color="grey400",
                                        ),
                                        ft.ElevatedButton(
                                            "Utiliser ce modèle",
                                            on_click=lambda e: self.charger_modele(
                                                "FACTURE"
                                            ),
                                        ),
                                    ],
                                    spacing=8,
                                ),
                            ),
                            ft.Container(
                                col={"sm": 12, "md": 4},
                                padding=12,
                                bgcolor="#1e293b",
                                border_radius=8,
                                content=ft.Column(
                                    [
                                        ft.Text(
                                            "📄 Suivi Devis / Proposal",
                                            weight="bold",
                                            size=14,
                                            color="#93C5FD",
                                        ),
                                        ft.Text(
                                            "Relance un prospect suite au dépôt d'un"
                                            " devis commercial.",
                                            size=12,
                                            color="grey400",
                                        ),
                                        ft.ElevatedButton(
                                            "Utiliser ce modèle",
                                            on_click=lambda e: self.charger_modele(
                                                "DEVIS"
                                            ),
                                        ),
                                    ],
                                    spacing=8,
                                ),
                            ),
                            ft.Container(
                                col={"sm": 12, "md": 4},
                                padding=12,
                                bgcolor="#1e293b",
                                border_radius=8,
                                content=ft.Column(
                                    [
                                        ft.Text(
                                            "📢 Communication Clients",
                                            weight="bold",
                                            size=14,
                                            color="#93C5FD",
                                        ),
                                        ft.Text(
                                            "Annonce d'une nouveauté, mise à jour ou"
                                            " information générale.",
                                            size=12,
                                            color="grey400",
                                        ),
                                        ft.ElevatedButton(
                                            "Utiliser ce modèle",
                                            on_click=lambda e: self.charger_modele(
                                                "INFO"
                                            ),
                                        ),
                                    ],
                                    spacing=8,
                                ),
                            ),
                        ],
                        spacing=10,
                    ),
                ],
                spacing=15,
                scroll="auto",
            ),
        )

    def _build_tab_historique(self):
        self.charger_table_historique()
        return ft.Container(
            padding=15,
            content=ft.Column(
                [
                    ft.Text(
                        "📜 Historique des communications", size=16, weight="bold"
                    ),
                    ft.Container(
                        padding=10,
                        bgcolor="#1e293b",
                        border_radius=8,
                        border=ft.Border(
                            top=ft.BorderSide(1, "grey800"),
                            right=ft.BorderSide(1, "grey800"),
                            bottom=ft.BorderSide(1, "grey800"),
                            left=ft.BorderSide(1, "grey800"),
                        ),
                        content=ft.Row([self.table_historique], scroll="auto"),
                    ),
                ],
                spacing=12,
                scroll="auto",
            ),
        )

    def _build_tab_smtp(self):
        try:
            pad_top = ft.padding.only(top=15)
        except Exception:
            pad_top = 10

        return ft.Container(
            padding=15,
            content=ft.Column(
                [
                    ft.Text(
                        "⚙️ Configuration du serveur de messagerie (SMTP)",
                        size=16,
                        weight="bold",
                    ),
                    ft.Text(
                        "Configurez vos accès SMTP (ex: Gmail, Outlook, OVH) pour"
                        " expédier vos e-mails.",
                        size=12,
                        italic=True,
                        color="grey400",
                    ),
                    ft.ResponsiveRow([
                        self.input_smtp_host,
                        self.input_smtp_port,
                    ]),
                    ft.ResponsiveRow([
                        self.input_smtp_user,
                        self.input_smtp_pass,
                    ]),
                    ft.ResponsiveRow([
                        self.input_sender_name,
                        ft.Container(
                            content=self.check_smtp_tls,
                            padding=pad_top,
                            col={"sm": 12, "md": 6},
                        ),
                    ]),
                    ft.Divider(color="grey800"),
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                "💾 Sauvegarder les paramètres SMTP",
                                icon=get_icon("SAVE"),
                                bgcolor=self.accent_color,
                                color="white",
                                on_click=self.sauvegarder_smtp,
                            )
                        ],
                        alignment="end",
                    ),
                ],
                spacing=12,
                scroll="auto",
            ),
        )

    # ============================================================
    # LOGIQUE & GESTION DES ACTIONS
    # ============================================================

    def on_destinataires_change(self, e):
        self.input_email_manuel.visible = self.dd_destinataires.value == "MANUEL"
        self.safe_update()

    def on_attachment_picked(self, e: ft.FilePickerResultEvent):
        if e.files:
            for f in e.files:
                if f.path:
                    p = Path(f.path)
                    if p not in self.attachments:
                        self.attachments.append(p)
            self.rafraichir_attachments_ui()

    def rafraichir_attachments_ui(self):
        self.list_attachments.controls.clear()
        for p in self.attachments:
            self.list_attachments.controls.append(
                ft.Chip(
                    label=ft.Text(p.name, size=11),
                    on_delete=lambda e, path=p: self.supprimer_attachment(path),
                )
            )
        self.safe_update()

    def supprimer_attachment(self, path: Path):
        if path in self.attachments:
            self.attachments.remove(path)
            self.rafraichir_attachments_ui()

    def charger_modele(self, type_modele):
        entreprise_nom = self.entreprise_data.get("nom", "Notre Entreprise")

        if type_modele == "FACTURE":
            self.dd_destinataires.value = "CLIENTS"
            self.input_sujet.value = (
                f"[{entreprise_nom}] Relance : Facture en attente de règlement"
            )
            self.input_corps.value = (
                "Bonjour,\n\n"
                "Sauf erreur ou omission de notre part, nous constatons que le"
                " règlement de votre facture est à ce jour en attente.\n\n"
                "Nous vous remercions de bien vouloir procéder à son règlement dans"
                " les meilleurs délais ou de nous transmettre l'avis de virement"
                " correspondant.\n\n"
                "Si votre virement a déjà été effectué, veuillez ne pas tenir compte"
                " de ce message.\n\n"
                "Restant à votre entière disposition,\n"
                f"L'équipe {entreprise_nom}"
            )

        elif type_modele == "DEVIS":
            self.dd_destinataires.value = "PROSPECTS"
            self.input_sujet.value = f"[{entreprise_nom}] Suivi de votre devis"
            self.input_corps.value = (
                "Bonjour,\n\n"
                "Nous faisons suite à l'envoi de notre proposition commerciale /"
                " devis.\n\n"
                "Avez-vous eu l'occasion de prendre connaissance de notre offre ? Nous"
                " restons à votre entière disposition pour toute question,"
                " ajustement ou précision complémentaire.\n\n"
                "Dans l'attente de votre retour,\n\n"
                "Cordialement,\n"
                f"L'équipe {entreprise_nom}"
            )

        elif type_modele == "INFO":
            self.dd_destinataires.value = "TOUS"
            self.input_sujet.value = (
                f"[{entreprise_nom}] Information importante concernant nos services"
            )
            self.input_corps.value = (
                "Chers clients, chers partenaires,\n\n"
                "Nous souhaitons vous informer d'une mise à jour importante"
                " concernant nos services.\n\n"
                "[Précisez votre message ici]\n\n"
                "Nous vous remercions pour votre confiance continue.\n\n"
                "Bien cordialement,\n"
                f"L'équipe {entreprise_nom}"
            )

        self.input_email_manuel.visible = False
        self.safe_update()

    def collecter_emails_destinataires(self):
        emails = []
        choix = self.dd_destinataires.value

        if choix == "MANUEL":
            if self.input_email_manuel.value.strip():
                emails.append(self.input_email_manuel.value.strip())
            return emails

        clients = getattr(
            self.app, "clients", getattr(self.app, "membres", [])
        )
        prospects = getattr(self.app, "prospects", [])

        if choix in ["TOUS", "CLIENTS"]:
            for c in clients:
                em = c.get("email", "").strip()
                if em:
                    emails.append(em)

        if choix in ["TOUS", "PROSPECTS"]:
            for p in prospects:
                em = p.get("email", "").strip()
                if em:
                    emails.append(em)

        return list(set(emails))

    def sauvegarder_smtp(self, e):
        config_smtp = {
            "host": self.input_smtp_host.value.strip(),
            "port": int(self.input_smtp_port.value.strip() or 587),
            "use_tls": self.check_smtp_tls.value,
            "user": self.input_smtp_user.value.strip(),
            "password": self.input_smtp_pass.value,
            "sender_name": self.input_sender_name.value.strip(),
        }
        self.app.config_smtp = config_smtp
        if hasattr(self.app, "save_data"):
            self.app.save_data()
        self._show_snackbar("Paramètres SMTP enregistrés avec succès !")

    def envoyer_email(self, e):
        destinataires = self.collecter_emails_destinataires()
        if not destinataires:
            self._show_snackbar(
                "Aucun destinataire trouvé ou adresse invalide.", is_error=True
            )
            return

        if not self.input_sujet.value.strip() or not self.input_corps.value.strip():
            self._show_snackbar(
                "Veuillez renseigner le sujet et le message.", is_error=True
            )
            return

        config_smtp = getattr(self.app, "config_smtp", {})
        host = config_smtp.get("host")
        user = config_smtp.get("user")
        pwd = config_smtp.get("password")

        if not host or not user or not pwd:
            self._show_snackbar(
                "Configuration SMTP incomplète. Renseignez l'onglet Configuration"
                " SMTP.",
                is_error=True,
            )
            return

        self.btn_send.disabled = True
        self.progress_ring.visible = True
        self.safe_update()

        threading.Thread(
            target=self._process_envoi_smtp,
            args=(destinataires, config_smtp),
            daemon=True,
        ).start()

    def _process_envoi_smtp(self, destinataires, config_smtp):
        try:
            host = config_smtp.get("host")
            user = config_smtp.get("user")
            pwd = config_smtp.get("password")
            port = int(config_smtp.get("port", 587))
            use_tls = config_smtp.get("use_tls", True)
            sender_name = config_smtp.get("sender_name", "Mon Entreprise")

            server = smtplib.SMTP(host, port, timeout=12)
            if use_tls:
                server.starttls()
            server.login(user, pwd)

            for dest in destinataires:
                msg = MIMEMultipart()
                msg["From"] = f"{sender_name} <{user}>"
                msg["To"] = dest
                msg["Subject"] = self.input_sujet.value

                msg.attach(MIMEText(self.input_corps.value, "plain", "utf-8"))

                for attach_path in self.attachments:
                    if attach_path.exists():
                        with open(attach_path, "rb") as f:
                            part = MIMEBase("application", "octet-stream")
                            part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f'attachment; filename="{attach_path.name}"',
                        )
                        msg.attach(part)

                server.send_message(msg)

            server.quit()

            log_item = {
                "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "destinataires": f"{len(destinataires)} destinataire(s)",
                "sujet": self.input_sujet.value,
                "statut": "Envoyé avec succès",
            }
            if not hasattr(self.app, "mails_history"):
                self.app.mails_history = []
            self.app.mails_history.append(log_item)
            if hasattr(self.app, "save_data"):
                self.app.save_data()

            self._show_snackbar(
                f"🎉 Email envoyé avec succès à {len(destinataires)} destinataire(s) !"
            )
            self.attachments.clear()
            self.rafraichir_attachments_ui()
            self.input_sujet.value = ""
            self.input_corps.value = ""

        except Exception as ex:
            self._show_snackbar(f"Erreur d'envoi SMTP : {ex}", is_error=True)
        finally:
            self.btn_send.disabled = False
            self.progress_ring.visible = False
            self.safe_update()

    def charger_table_historique(self):
        self.table_historique.rows.clear()
        logs = getattr(self.app, "mails_history", [])
        for log in reversed(logs):
            self.table_historique.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(log.get("date", ""))),
                        ft.DataCell(ft.Text(log.get("destinataires", ""))),
                        ft.DataCell(ft.Text(log.get("sujet", ""))),
                        ft.DataCell(ft.Text(log.get("statut", ""), color="green400")),
                    ]
                )
            )

    def _show_snackbar(self, message: str, is_error: bool = False):
        color = "red700" if is_error else "green700"
        page_obj = getattr(self.app, "page", None) or self.page
        if page_obj:
            snack = ft.SnackBar(ft.Text(message), bgcolor=color)
            if hasattr(page_obj, "open"):
                try:
                    page_obj.open(snack)
                except Exception:
                    page_obj.snack_bar = snack
                    snack.open = True
            else:
                page_obj.snack_bar = snack
                snack.open = True
            self.safe_update()