import base64
import io
from pathlib import Path
import flet as ft
from PIL import Image as PILImage


def safe_border(width=1, color="#2A2A2E"):
    """Bordure universelle compatible toutes versions de Flet."""
    side = ft.BorderSide(width, color)
    return ft.Border(top=side, right=side, bottom=side, left=side)


class EntrepriseView(ft.Container):

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        self.padding = 10

        self.card_color = "#1E1E22"
        self.primary_color = "#2B719E"

        if hasattr(app, "data_dir"):
            self.data_folder = Path(app.data_dir)
        else:
            self.data_folder = (
                getattr(app, "base_dir", Path(__file__).resolve().parent.parent)
                / "data"
            )

        self.logo_path = self.data_folder / "logo.png"
        self.entreprise = getattr(app, "entreprise", {})
        self.file_picker = None

        self.init_default_values()
        self._build_interface()

    def _get_page(self, e=None):
        """Récupère l'instance de la page de manière fiable."""
        if e and hasattr(e, "control") and e.control and getattr(e.control, "page", None):
            return e.control.page
        if e and hasattr(e, "page") and getattr(e, "page", None):
            return e.page
        if self.page:
            return self.page
        return getattr(self.app, "page", None)

    def safe_update(self):
        """Met à jour le composant de manière sécurisée."""
        page = self._get_page()
        if page:
            try:
                page.update()
            except Exception:
                try:
                    self.update()
                except Exception:
                    pass

    def did_mount(self):
        """S'exécute à l'affichage de la vue."""
        self._update_logo_preview()

    def init_default_values(self):
        """S'assure que les variables de configuration existent en mémoire."""
        defaults = {
            "nom": "VOTRE ENTREPRISE",
            "statut_juridique": "Micro-entreprise",
            "siret": "",
            "adresse": "",
            "telephone": "",
            "email": "",
            "iban": "",
            "bic": "",
            "taux_charges": "21.1",
            "soumis_tva": "Non",
            "assujetti_tva": False,
            "tva_activee": False,
            "taux_tva": "0.0",
            "tva_par_defaut": "0.0",
            "taux_tva_defaut": "0.0",
            "mention_tva": "TVA non applicable, art. 293 B du CGI",
            "rc_pro": (
                "Assurance RC Pro & Décennale : [Nom Compagnie] - Contrat n° [0000]"
                " - Zone : [France]"
            ),
            "conditions_reglement": (
                "Paiement à réception. Pénalités de retard : 3 fois le taux d’intérêt"
                " légal. Indemnité forfaitaire de 40€ pour frais de recouvrement."
            ),
        }
        for key, default_val in defaults.items():
            if key not in self.entreprise or self.entreprise[key] is None:
                self.entreprise[key] = default_val

    def _build_interface(self):
        # --- 1. SECTION LOGO ---
        self.img_logo = ft.Image(
            src="",
            width=120,
            height=60,
            fit="contain",
            visible=False,
        )
        self.lbl_no_logo = ft.Text("Aucun logo configuré", color="#AEAEB2")

        logo_card = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Logo officiel pour les PDF :",
                        size=13,
                        weight="bold",
                    ),
                    ft.Row(
                        [
                            ft.Row(
                                [self.img_logo, self.lbl_no_logo],
                                alignment=ft.MainAxisAlignment.START,
                            ),
                            ft.ElevatedButton(
                                "🖼️ Changer le logo",
                                bgcolor=self.primary_color,
                                color="white",
                                icon="image_rounded",
                                on_click=self._open_file_picker,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                        run_spacing=10,
                    ),
                ],
                spacing=10,
            ),
            bgcolor=self.card_color,
            border=safe_border(1, "#2A2A2E"),
            border_radius=8,
            padding=12,
        )

        # --- 2. SECTION CONFIGURATION ET OPTIONS ---
        statut_options = [
            "Micro-entreprise",
            "EI (Entreprise Individuelle)",
            "EURL",
            "SARL",
            "SASU",
            "SAS",
        ]
        current_statut = self.entreprise.get(
            "statut_juridique", "Micro-entreprise"
        )
        if current_statut not in statut_options:
            statut_options.append(current_statut)

        self.dd_statut = ft.Dropdown(
            label="Type d'entreprise",
            options=[ft.dropdown.Option(opt) for opt in statut_options],
            value=current_statut,
        )

        is_soumis = (
            self.entreprise.get("soumis_tva") == "Oui"
            or self.entreprise.get("tva_activee") is True
            or self.entreprise.get("assujetti_tva") is True
        )

        self.rg_tva = ft.RadioGroup(
            content=ft.Row(
                [
                    ft.Radio(value="Non", label="Non (Franchise)"),
                    ft.Radio(value="Oui", label="Oui (Assujetti)"),
                ],
                wrap=True,
                spacing=15,
            ),
            value="Oui" if is_soumis else "Non",
            on_change=self._on_tva_change,
        )

        taux_actuel = str(
            self.entreprise.get(
                "tva_par_defaut", self.entreprise.get("taux_tva", "20.0" if is_soumis else "0.0")
            )
        )
        if not is_soumis:
            taux_actuel = "0.0"

        self.tf_taux_tva = ft.TextField(
            label="Taux TVA (%)",
            value=taux_actuel,
            width=130,
            visible=is_soumis,
        )

        options_card = ft.Container(
            content=ft.Column(
                [
                    self.dd_statut,
                    ft.Column(
                        [
                            ft.Text(
                                "Soumis à la TVA :",
                                weight="bold",
                                size=13,
                            ),
                            ft.Row([self.rg_tva, self.tf_taux_tva], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ],
                        spacing=8,
                    ),
                ],
                spacing=15,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            bgcolor="transparent",
        )

        # --- 3. SECTION MENTIONS LÉGALES OBLIGATOIRES ---
        self.tf_legal_tva = ft.TextField(
            label="Mention d'application / Exonération de TVA",
            value=str(self.entreprise.get("mention_tva", "")),
            multiline=True,
            min_lines=2,
        )
        self.tf_rc_pro = ft.TextField(
            label="Assurance Décennale / RC Professionnelle",
            value=str(self.entreprise.get("rc_pro", "")),
            multiline=True,
            min_lines=2,
        )
        self.tf_conditions = ft.TextField(
            label="Conditions de règlement & Pénalités par défaut",
            value=str(self.entreprise.get("conditions_reglement", "")),
            multiline=True,
            min_lines=2,
        )

        legal_card = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "📜 Mentions Légales Obligatoires (Pied de page PDF)",
                        size=14,
                        weight="bold",
                        color=self.primary_color,
                    ),
                    ft.Divider(height=1, color="#2A2A2E"),
                    self.tf_legal_tva,
                    self.tf_rc_pro,
                    self.tf_conditions,
                ],
                spacing=15,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            bgcolor=self.card_color,
            border=safe_border(1, "#2A2A2E"),
            border_radius=8,
            padding=15,
        )

        # --- 4. SECTION COORDONNÉES CLASSIQUES ---
        form_fields = [
            ("nom", "Nom de l'entreprise / Commercial :"),
            ("siret", "Numéro SIRET (14 chiffres) :"),
            ("adresse", "Adresse postale complète :"),
            ("telephone", "Numéro de téléphone :"),
            ("email", "Adresse e-mail de contact :"),
            ("iban", "Code IBAN :"),
            ("bic", "Code BIC / SWIFT :"),
            ("taux_charges", "Taux de charges URSSAF % (ex: 21.1) :"),
        ]

        self.entries = {}
        coordonnees_controls = [
            ft.Text(
                "📍 Coordonnées & Identification",
                size=14,
                weight="bold",
                color=self.primary_color,
            ),
            ft.Divider(height=1, color="#2A2A2E"),
        ]

        for key, label_text in form_fields:
            is_multiline = key == "adresse"
            tf = ft.TextField(
                label=label_text,
                value=str(self.entreprise.get(key, "")),
                multiline=is_multiline,
                min_lines=2 if is_multiline else 1,
            )
            coordonnees_controls.append(tf)
            self.entries[key] = tf

        coordonnees_card = ft.Container(
            content=ft.Column(
                coordonnees_controls,
                spacing=15,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            bgcolor=self.card_color,
            border=safe_border(1, "#2A2A2E"),
            border_radius=8,
            padding=15,
        )

        # --- CONTENU GLOBAL DÉFILANT ---
        header = ft.Row(
            controls=[
                ft.Text(
                    "🏢 Réglages Entreprise",
                    size=22,
                    weight="bold",
                ),
                ft.ElevatedButton(
                    "💾 Enregistrer",
                    bgcolor=self.primary_color,
                    color="white",
                    icon="save_rounded",
                    on_click=self._save_company,
                    height=40,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            wrap=True,
            run_spacing=10,
        )

        self.content = ft.Column(
            controls=[
                header,
                ft.Container(height=5),
                logo_card,
                options_card,
                legal_card,
                coordonnees_card,
                ft.Container(height=20),
            ],
            spacing=15,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _open_file_picker(self, e):
        page = self._get_page(e)
        if not page:
            return

        # Correction : réutilisation d'une instance unique dans overlay pour éviter la fuite mémoire
        if not self.file_picker:
            self.file_picker = ft.FilePicker()
            self.file_picker.on_result = self._import_company_logo

        if self.file_picker not in page.overlay:
            page.overlay.append(self.file_picker)
            try:
                page.update()
            except Exception:
                pass

        try:
            self.file_picker.pick_files(
                dialog_title="Choisir une image de logo",
                file_type=ft.FilePickerFileType.IMAGE,
                allowed_extensions=["png", "jpg", "jpeg"],
            )
        except Exception as ex:
            self.show_snack(f"Erreur d'ouverture du sélecteur : {ex}", is_error=True, e=e)

    def _import_company_logo(self, e: ft.FilePickerResultEvent):
        # Correction : vérification robuste de l'existence du fichier et lecture sécurisée des octets (compatible Android/Desktop)
        if not e.files or len(e.files) == 0:
            return

        file_info = e.files[0]
        file_path = file_info.path

        if not file_path or not Path(file_path).exists():
            self.show_snack("Impossible d'accéder au chemin du fichier sélectionné.", is_error=True, e=e)
            return

        try:
            self.logo_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, "rb") as f:
                img_data = f.read()

            img = PILImage.open(io.BytesIO(img_data))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGBA")
            else:
                img = img.convert("RGB")
            img.save(self.logo_path, "PNG")

            self._update_logo_preview()
            self.show_snack("Le logo de l'entreprise a été mis à jour avec succès ! ✅", e=e)
        except Exception as ex:
            print(f"[ERROR] _import_company_logo: {ex}")
            self.show_snack(f"Erreur d'importation : {ex}", is_error=True, e=e)

    def _on_tva_change(self, e):
        if self.rg_tva.value == "Oui":
            if self.tf_taux_tva.value in ["0", "0.0", "0,0", ""]:
                self.tf_taux_tva.value = "20.0"
            self.tf_legal_tva.value = (
                "Assujetti à la TVA - Numéro d'identification : [Votre N° TVA]"
            )
            self.tf_taux_tva.visible = True
        else:
            self.tf_taux_tva.value = "0.0"
            self.tf_legal_tva.value = "TVA non applicable, art. 293 B du CGI"
            self.tf_taux_tva.visible = False
        self.safe_update()

    def _update_logo_preview(self):
        if self.logo_path.exists():
            try:
                with open(self.logo_path, "rb") as img_file:
                    encoded_string = base64.b64encode(img_file.read()).decode("utf-8")

                self.img_logo.src_base64 = encoded_string
                self.img_logo.visible = True
                self.lbl_no_logo.visible = False
            except Exception as e:
                self.lbl_no_logo.value = "Erreur de lecture du logo"
                self.lbl_no_logo.visible = True
                self.img_logo.visible = False
                print(f"[WARN] _update_logo_preview: {e}")
        else:
            self.lbl_no_logo.value = "Aucun logo configuré"
            self.lbl_no_logo.visible = True
            self.img_logo.visible = False

        self.safe_update()

    def _save_company(self, e):
        taux_brut = self.entries["taux_charges"].value.strip()
        taux_propre = (
            taux_brut.replace("%", "").replace(" ", "").replace(",", ".").strip()
        )

        if taux_propre:
            try:
                float(taux_propre)
            except ValueError:
                self.show_snack(
                    "Le taux de charges URSSAF doit être un nombre valide (ex: 21.1 ou 21,1).",
                    is_error=True,
                    e=e,
                )
                return
        else:
            taux_propre = "0.0"

        is_soumis = self.rg_tva.value == "Oui"

        if is_soumis:
            taux_tva_brut = self.tf_taux_tva.value.strip().replace(",", ".")
            try:
                float(taux_tva_brut) if taux_tva_brut else 20.0
            except ValueError:
                self.show_snack("Le taux de TVA doit être un nombre valide (ex: 20.0).", is_error=True, e=e)
                return
            val_taux_tva = taux_tva_brut if taux_tva_brut else "20.0"
        else:
            val_taux_tva = "0.0"

        self.entreprise["statut_juridique"] = self.dd_statut.value
        self.entreprise["soumis_tva"] = "Oui" if is_soumis else "Non"
        self.entreprise["assujetti_tva"] = is_soumis
        self.entreprise["tva_activee"] = is_soumis

        self.entreprise["taux_tva"] = val_taux_tva
        self.entreprise["tva_par_defaut"] = val_taux_tva
        self.entreprise["taux_tva_defaut"] = val_taux_tva

        self.entreprise["mention_tva"] = self.tf_legal_tva.value.strip()
        self.entreprise["rc_pro"] = self.tf_rc_pro.value.strip()
        self.entreprise["conditions_reglement"] = self.tf_conditions.value.strip()

        for key in self.entries:
            if key == "taux_charges":
                self.entreprise[key] = taux_propre
            else:
                self.entreprise[key] = self.entries[key].value.strip()

        if hasattr(self.app, "save_data"):
            self.app.save_data()

        if hasattr(self.app, "creer_menu_sidebar"):
            self.app.creer_menu_sidebar()

        self.show_snack("Les informations et mentions légales ont été enregistrées avec succès. ✅", e=e)

    def show_snack(self, message, is_error=False, e=None):
        page = self._get_page(e)
        if not page:
            return
        snack = ft.SnackBar(
            content=ft.Text(message),
            bgcolor="#B91C1C" if is_error else "#15803D",
        )
        try:
            page.open(snack)
        except Exception:
            page.snack_bar = snack
            snack.open = True
            page.update()