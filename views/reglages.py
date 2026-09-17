import json
from pathlib import Path
import shutil
import zipfile
import flet as ft


def safe_border(width=1, color="#2A2A32"):
    """Bordure universelle sécurisée compatible Desktop et Mobile."""
    side = ft.BorderSide(width, color)
    return ft.Border(top=side, right=side, bottom=side, left=side)


def safe_padding_only(top=0, right=0, bottom=0, left=0):
    """Padding sécurisé compatible avec toutes les versions et plateformes Flet."""
    if hasattr(ft, "padding") and hasattr(ft.padding, "only"):
        try:
            return ft.padding.only(top=top, right=right, bottom=bottom, left=left)
        except Exception:
            pass
    return top


class ReglagesView(ft.Container):

    def __init__(self, app):
        super().__init__(expand=True, padding=15)
        self.app = app

        # Récupération de la couleur d'accentuation actuelle
        self.entreprise_data = getattr(
            self.app, "entreprise", getattr(self.app, "association", {})
        )
        self.accent_color = self.entreprise_data.get("accent_color", "#2B719E")

        # Suppression de l'instanciation locale bloquante des FilePickers.
        # Ils seront gérés globalement sur l'overlay de la page principale.
        self.mapping_couleurs = {
            "Bleu": "#2B719E",
            "Vert": "#2E7D32",
            "Orange": "#D97706",
            "Violet": "#6D28D9",
            "Rouge": "#C62828",
        }

        self._build_interface()

    def get_page(self):
        """Récupère l'instance active de la page Flet."""
        return self.page or getattr(self.app, "page", None)

    def safe_update(self):
        """Mise à jour sécurisée de l'UI."""
        page_obj = self.get_page()
        if page_obj:
            try:
                page_obj.update()
            except Exception:
                pass

    def did_mount(self):
        """Chargement initial des données au montage de la vue."""
        if hasattr(self.app, "load_data"):
            self.app.load_data()
        self.safe_update()

    def _build_interface(self):
        # 1. Thème Apparence
        theme_btn = ft.SegmentedButton(
            segments=[
                ft.Segment(value="Dark", label=ft.Text("Sombre")),
                ft.Segment(value="Light", label=ft.Text("Clair")),
            ],
            selected=[self.entreprise_data.get("theme_pref", "Dark")],
            on_change=self._changer_theme,
        )

        # 2. Couleur de l'application
        color_btn = ft.SegmentedButton(
            segments=[
                ft.Segment(value=k, label=ft.Text(k))
                for k in self.mapping_couleurs.keys()
            ],
            selected=[self.entreprise_data.get("accent_color_name", "Bleu")],
            on_change=self._changer_couleur_theme,
        )

        # 3. Sauvegarde Locale
        backup_row = ft.Row(
            controls=[
                ft.ElevatedButton(
                    "Créer un Backup Global",
                    bgcolor="#15803D",
                    color="white",
                    on_click=self._faire_sauvegarde,
                    expand=True,
                ),
                ft.ElevatedButton(
                    "Restaurer",
                    bgcolor="#B91C1C",
                    color="white",
                    on_click=self._restaurer_sauvegarde,
                    expand=True,
                ),
            ],
            spacing=10,
        )

        # 4. Sauvegarde Cloud
        cloud_column = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.ElevatedButton(
                            "Exporter vers Cloud",
                            bgcolor="#1D4ED8",
                            color="white",
                            on_click=lambda e: self.show_snack(
                                "Poussée Cloud à implémenter selon votre API."
                            ),
                            expand=True,
                        ),
                        ft.ElevatedButton(
                            "Importer du Cloud",
                            bgcolor="#1E3A8A",
                            color="white",
                            on_click=lambda e: self.show_snack(
                                "Récupération Cloud à implémenter selon votre API."
                            ),
                            expand=True,
                        ),
                    ],
                    spacing=10,
                ),
                ft.ElevatedButton(
                    "🔧 Configurer les accès Cloud",
                    on_click=self._popup_cloud,
                    width=600,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8)
                    ),
                ),
            ],
            spacing=5,
        )

        # 5. Numérotation Séquentielle
        num_btn = ft.ElevatedButton(
            "Modifier les Séquences",
            on_click=self._popup_numerotation,
            width=600,
        )

        # 6. Messagerie SMTP / IMAP
        email_btn = ft.ElevatedButton(
            "Configurer la Messagerie",
            on_click=self._popup_email,
            width=600,
        )

        # 7. Facturation Dématérialisée (Factur-X)
        etat_initial = self.entreprise_data.get("demat_active", False)
        demat_switch = ft.Switch(
            label="Activer le format Factur-X",
            value=etat_initial,
            on_change=lambda e: self._toggle_demat(e.control.value),
        )
        demat_column = ft.Column(
            controls=[
                demat_switch,
                ft.ElevatedButton(
                    "Options avancées Chorus Pro",
                    on_click=self._popup_demat,
                    width=600,
                ),
            ],
            spacing=5,
        )

        # 8. Seuils de CA
        seuils_btn = ft.ElevatedButton(
            "Gérer mes alertes de CA",
            on_click=self._popup_seuils,
            width=600,
        )

        # Assemblage principal
        self.content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            "⚙️ Paramètres & Configuration",
                            size=24,
                            weight="bold",
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                ft.Container(
                    content=ft.ResponsiveRow(
                        controls=[
                            self._creer_base_card(
                                "🎨 Apparence & Mode",
                                "Basculez entre le mode sombre et le mode clair.",
                                theme_btn,
                            ),
                            self._creer_base_card(
                                "✨ Couleur de l'application",
                                "Choisissez la couleur d'accentuation des boutons du logiciel.",
                                color_btn,
                            ),
                            self._creer_base_card(
                                "💾 Sauvegarde Locale",
                                "Sécurisez vos factures, devis, fiches clients et agenda en local.",
                                backup_row,
                            ),
                            self._creer_base_card(
                                "☁️ Sauvegarde Cloud",
                                "Synchronisez et récupérez vos bases de données depuis un serveur distant.",
                                cloud_column,
                            ),
                            self._creer_base_card(
                                "🔢 Structure des Numéros",
                                "Définissez le format séquentiel de vos factures et devis.",
                                num_btn,
                            ),
                            self._creer_base_card(
                                "📧 Configuration Messagerie",
                                "Paramétrez l'envoi (SMTP) et la réception (IMAP) de vos e-mails.",
                                email_btn,
                            ),
                            self._creer_base_card(
                                "🧾 Facturation Dématérialisée",
                                "Préparez la transition légale obligatoire vers Chorus Pro.",
                                demat_column,
                            ),
                            self._creer_base_card(
                                "⚠️ Seuils & Plafonds de CA",
                                "Suivez vos limites de Chiffre d'Affaires d'auto-entrepreneur.",
                                seuils_btn,
                            ),
                        ],
                        spacing=15,
                    ),
                    expand=True,
                ),
            ],
            spacing=20,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _creer_base_card(self, titre, description, content_control):
        """Génère un conteneur de carte stylisé et responsive."""
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(titre, size=15, weight="bold"),
                    ft.Text(description, size=12, color="#AEAEB2"),
                    ft.Container(
                        content=content_control, padding=safe_padding_only(top=5)
                    ),
                ],
                spacing=5,
                tight=True,
            ),
            bgcolor="#1E1E20",
            border_radius=12,
            border=safe_border(1, "#2A2A2E"),
            padding=15,
            col={"xs": 12, "sm": 6},
        )

    def _get_active_data_dir(self):
        if hasattr(self.app, "data_dir"):
            return Path(self.app.data_dir)
        return Path(".").resolve() / "data"

    # --- ACTIONS THÈMES ---
    def _changer_theme(self, e):
        selected_val = list(e.control.selected) if e.control.selected else ["Dark"]
        choix = selected_val[0]
        page_obj = self.get_page()
        if page_obj:
            page_obj.theme_mode = (
                ft.ThemeMode.DARK if choix == "Dark" else ft.ThemeMode.LIGHT
            )
        self.entreprise_data["theme_pref"] = choix
        if hasattr(self.app, "save_data"):
            self.app.save_data()
        self.safe_update()

    def _changer_couleur_theme(self, e):
        if not e.control.selected:
            return
        nom_couleur = list(e.control.selected)[0]
        hex_color = self.mapping_couleurs.get(nom_couleur, "#2B719E")
        self.entreprise_data.update(
            {"accent_color_name": nom_couleur, "accent_color": hex_color}
        )
        self.accent_color = hex_color
        if hasattr(self.app, "save_data"):
            self.app.save_data()
        self.show_snack(
            f"Teinte globale {nom_couleur} enregistrée. Redémarrez pour appliquer partout."
        )

    def _toggle_demat(self, valeur):
        self.entreprise_data["demat_active"] = bool(valeur)
        if hasattr(self.app, "save_data"):
            self.app.save_data()

    # --- SAUVEGARDES & RESTAURATION (Corrigés avec FilePicker global) ---
    def _faire_sauvegarde(self, e):
        page_obj = self.get_page()
        if not page_obj:
            return

        # Gestion centralisée d'un picker d'export global rattaché à la page
        if not hasattr(page_obj, "global_export_picker"):
            page_obj.global_export_picker = ft.FilePicker(on_result=self._on_export_result)
            page_obj.overlay.append(page_obj.global_export_picker)
            page_obj.update()
        else:
            page_obj.global_export_picker.on_result = self._on_export_result

        try:
            page_obj.global_export_picker.save_file(
                dialog_title="Enregistrer la sauvegarde globale",
                file_name="backup_global.zip",
                allowed_extensions=["zip"],
            )
        except Exception as ex:
            self.show_snack(f"Erreur d'ouverture du sélecteur : {ex}", is_error=True)

    def _on_export_result(self, e: ft.FilePickerResultEvent):
        if e.path:
            try:
                data_dir = self._get_active_data_dir()
                with zipfile.ZipFile(e.path, "w", zipfile.ZIP_DEFLATED) as z:
                    for f in ["database.json", "application.db"]:
                        if (data_dir / f).exists():
                            z.write(data_dir / f, arcname=f)
                self.show_snack("Sauvegarde globale exportée avec succès ! ✔")
            except Exception as ex:
                self.show_snack(
                    f"Erreur d'écriture du backup : {ex}", is_error=True
                )

    def _restaurer_sauvegarde(self, e):
        def confirmation_action(action_confirmee):
            self._fermer_dialogue(dialog)
            if action_confirmee:
                page_obj = self.get_page()
                if page_obj:
                    # Gestion centralisée d'un picker d'import global rattaché à la page
                    if not hasattr(page_obj, "global_import_picker"):
                        page_obj.global_import_picker = ft.FilePicker(on_result=self._on_import_result)
                        page_obj.overlay.append(page_obj.global_import_picker)
                        page_obj.update()
                    else:
                        page_obj.global_import_picker.on_result = self._on_import_result

                    try:
                        page_obj.global_import_picker.pick_files(
                            allowed_extensions=["zip"],
                            dialog_title="Sélectionnez une sauvegarde (.zip)",
                        )
                    except Exception as ex:
                        self.show_snack(
                            f"Erreur d'ouverture du sélecteur : {ex}",
                            is_error=True,
                        )

        dialog = ft.AlertDialog(
            title=ft.Text("🚨 Attention"),
            content=ft.Text(
                "Êtes-vous sûr de vouloir écraser les données actuelles ?"
                " Cette action est irréversible."
            ),
            actions=[
                ft.TextButton(
                    "Annuler",
                    on_click=lambda _: confirmation_action(False),
                ),
                ft.ElevatedButton(
                    "Confirmer l'écrasement",
                    bgcolor="#B91C1C",
                    color="white",
                    on_click=lambda _: confirmation_action(True),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._ouvrir_dialogue(dialog)

    def _on_import_result(self, e: ft.FilePickerResultEvent):
        if e.files and e.files[0].path:
            try:
                data_dir = self._get_active_data_dir()
                data_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(e.files[0].path, "r") as z:
                    z.extractall(data_dir)
                if hasattr(self.app, "load_data"):
                    self.app.load_data()
                self.show_snack(
                    "Données locales restaurées et synchronisées ! ✔"
                )
            except Exception as ex:
                self.show_snack(
                    f"Échec du déploiement de l'archive : {ex}", is_error=True
                )

    # --- ABSTRACTION MODALE ---
    def _ouvrir_dialogue(self, dlg):
        page_obj = self.get_page()
        if page_obj:
            try:
                page_obj.open(dlg)
            except Exception:
                dlg.open = True
                if dlg not in page_obj.overlay:
                    page_obj.overlay.append(dlg)
                page_obj.update()

    def _fermer_dialogue(self, dlg):
        page_obj = self.get_page()
        if page_obj:
            try:
                page_obj.close(dlg)
            except Exception:
                dlg.open = False
                page_obj.update()

    def _ouvrir_popup_formulaire(
        self, titre, liste_champs, callback_sauvegarde
    ):
        """Crée une fenêtre de saisie modale propre et adaptée aux mobiles."""

        def fermer(e):
            self._fermer_dialogue(dialog)

        def valider(e):
            if callback_sauvegarde():
                self._fermer_dialogue(dialog)

        dialog = ft.AlertDialog(
            title=ft.Text(titre, size=18, weight="bold"),
            content=ft.Container(
                content=ft.Column(
                    controls=liste_champs,
                    spacing=12,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=420,
                height=420,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=fermer),
                ft.ElevatedButton(
                    "Enregistrer",
                    bgcolor=self.accent_color,
                    color="white",
                    on_click=valider,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._ouvrir_dialogue(dialog)

    # --- CONFIGURATIONS FORMULAIRES ---
    def _popup_email(self, e):
        ent = self.entreprise_data
        tf_host = ft.TextField(
            label="Serveur d'envoi SMTP",
            value=ent.get("smtp_host", "smtp.gmail.com"),
            bgcolor="#1A1A1C",
        )
        tf_port = ft.TextField(
            label="Port SMTP (ex: 465)",
            value=ent.get("smtp_port", "465"),
            bgcolor="#1A1A1C",
        )
        tf_imap = ft.TextField(
            label="Serveur de réception IMAP",
            value=ent.get("imap_host", "imap.gmail.com"),
            bgcolor="#1A1A1C",
        )
        tf_imap_port = ft.TextField(
            label="Port IMAP (ex: 993)",
            value=ent.get("imap_port", "993"),
            bgcolor="#1A1A1C",
        )
        tf_user = ft.TextField(
            label="Adresse e-mail / Identifiant",
            value=ent.get("smtp_user", "saillyfranch276@gmail.com"),
            bgcolor="#1A1A1C",
        )
        tf_pass = ft.TextField(
            label="Mot de passe d'application",
            value=ent.get("smtp_password", ""),
            password=True,
            can_reveal_password=True,
            bgcolor="#1A1A1C",
        )

        def sauve():
            ent.update(
                {
                    "smtp_host": tf_host.value.strip(),
                    "smtp_port": tf_port.value.strip(),
                    "imap_host": tf_imap.value.strip(),
                    "imap_port": tf_imap_port.value.strip(),
                    "smtp_user": tf_user.value.strip(),
                    "smtp_password": tf_pass.value.strip(),
                }
            )
            if hasattr(self.app, "save_data"):
                self.app.save_data()
            self.show_snack("Configuration Email mise à jour ! ✔")
            return True

        self._ouvrir_popup_formulaire(
            "Messagerie (SMTP & IMAP)",
            [tf_host, tf_port, tf_imap, tf_imap_port, tf_user, tf_pass],
            sauve,
        )

    def _popup_cloud(self, e):
        ent = self.entreprise_data
        dd_prov = ft.Dropdown(
            label="Fournisseur Cloud",
            options=[
                ft.dropdown.Option(p)
                for p in [
                    "Google Drive",
                    "Dropbox",
                    "OneDrive",
                    "Serveur FTP/SFTP",
                    "WebDAV",
                ]
            ],
            value=ent.get("cloud_provider", "Google Drive"),
            bgcolor="#1A1A1C",
        )
        tf_id = ft.TextField(
            label="Client ID / Identifiant",
            value=ent.get("cloud_id", ""),
            bgcolor="#1A1A1C",
        )
        tf_secret = ft.TextField(
            label="Client Secret / Mot de passe",
            value=ent.get("cloud_secret", ""),
            password=True,
            can_reveal_password=True,
            bgcolor="#1A1A1C",
        )
        tf_url = ft.TextField(
            label="URL / Chemin distant",
            value=ent.get("cloud_url", ""),
            bgcolor="#1A1A1C",
        )

        def sauve():
            ent.update(
                {
                    "cloud_provider": dd_prov.value,
                    "cloud_id": tf_id.value.strip(),
                    "cloud_secret": tf_secret.value.strip(),
                    "cloud_url": tf_url.value.strip(),
                }
            )
            if hasattr(self.app, "save_data"):
                self.app.save_data()
            self.show_snack("Configuration Accès Cloud sauvegardée ! ✔")
            return True

        self._ouvrir_popup_formulaire(
            "Configuration Paramètres Cloud",
            [dd_prov, tf_id, tf_secret, tf_url],
            sauve,
        )

    def _popup_numerotation(self, e):
        ent = self.entreprise_data
        tf_f = ft.TextField(
            label="Préfixe des Factures",
            value=ent.get("prefix_facture", "F2026-"),
            bgcolor="#1A1A1C",
        )
        tf_d = ft.TextField(
            label="Préfixe des Devis",
            value=ent.get("prefix_devis", "D2026-"),
            bgcolor="#1A1A1C",
        )

        def sauve():
            ent.update(
                {
                    "prefix_facture": tf_f.value.strip(),
                    "prefix_devis": tf_d.value.strip(),
                }
            )
            if hasattr(self.app, "save_data"):
                self.app.save_data()
            self.show_snack("Préfixes séquentiels modifiés ! ✔")
            return True

        self._ouvrir_popup_formulaire(
            "Séquences de numérotation", [tf_f, tf_d], sauve
        )

    def _popup_demat(self, e):
        ent = self.entreprise_data
        tf_c = ft.TextField(
            label="Numéro d'identifiant Chorus Pro (Siret / Tech)",
            value=ent.get("chorus_id", ""),
            bgcolor="#1A1A1C",
        )

        def sauve():
            ent["chorus_id"] = tf_c.value.strip()
            if hasattr(self.app, "save_data"):
                self.app.save_data()
            self.show_snack("Identifiant Chorus Pro enregistré ! ✔")
            return True

        self._ouvrir_popup_formulaire("Identifiants Chorus Pro", [tf_c], sauve)

    def _popup_seuils(self, e):
        ent = self.entreprise_data
        tf_s = ft.TextField(
            label="Plafond ou Seuil d'alerte (€)",
            value=str(ent.get("seuil_alerte_ca", 70000)),
            bgcolor="#1A1A1C",
        )

        def sauve():
            try:
                raw_val = (
                    (tf_s.value or "0")
                    .replace(" ", "")
                    .replace(",", ".")
                    .strip()
                )
                ent["seuil_alerte_ca"] = float(raw_val)
                if hasattr(self.app, "save_data"):
                    self.app.save_data()
                self.show_snack("Seuil de sécurité CA mis à jour ! ✔")
                return True
            except ValueError:
                self.show_snack(
                    "Veuillez entrer une valeur numérique valide.",
                    is_error=True,
                )
                return False

        self._ouvrir_popup_formulaire(
            "Seuils de Chiffre d'Affaires", [tf_s], sauve
        )

    def show_snack(self, message: str, is_error: bool = False):
        color = "#B91C1C" if is_error else "#15803D"
        page_obj = self.get_page()
        if page_obj:
            snack = ft.SnackBar(content=ft.Text(message), bgcolor=color)
            try:
                page_obj.open(snack)
            except Exception:
                page_obj.snack_bar = snack
                snack.open = True
                page_obj.update()
