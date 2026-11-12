from django import forms

from .models import (
    Equipo,
    Jugador,
    normalizar_nombre_completo,
    validar_cedula_ecuatoriana,
)


class ReemplazarEquipoFicticioForm(forms.Form):
    nombre = forms.CharField(
        max_length=120,
        label="Nombre del equipo real",
        widget=forms.TextInput(
            attrs={
                "class": "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm",
                "placeholder": "Nombre del equipo",
                "autocomplete": "off",
            }
        ),
    )


class EquipoForm(forms.ModelForm):
    dirigente_1 = forms.CharField(
        label="Dirigente 1",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-100",
                "placeholder": "Nombre completo",
                "autocomplete": "off",
            }
        ),
    )
    dirigente_2 = forms.CharField(
        label="Dirigente 2 (opcional)",
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-100",
                "placeholder": "Nombre completo",
                "autocomplete": "off",
            }
        ),
    )
    dirigente_3 = forms.CharField(
        label="Dirigente 3 (opcional)",
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-100",
                "placeholder": "Nombre completo",
                "autocomplete": "off",
            }
        ),
    )
    dirigente_prioritario = forms.ChoiceField(
        label="Contacto prioritario",
        choices=(
            ("1", "Dirigente 1"),
            ("2", "Dirigente 2"),
            ("3", "Dirigente 3"),
        ),
        widget=forms.RadioSelect,
        error_messages={"required": "Selecciona un dirigente prioritario."},
    )
    telefono_prioritario = forms.CharField(
        label="Teléfono del dirigente prioritario",
        max_length=30,
        widget=forms.TextInput(
            attrs={
                "class": "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-100",
                "placeholder": "Número de contacto",
                "autocomplete": "tel",
            }
        ),
    )
    correo_prioritario = forms.EmailField(
        label="Correo electrónico del dirigente prioritario",
        widget=forms.EmailInput(
            attrs={
                "class": "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-100",
                "placeholder": "nombre@correo.com",
                "autocomplete": "email",
            }
        ),
    )

    class Meta:
        model = Equipo
        fields = ["nombre"]
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-100",
                    "placeholder": "Ej. Deportivo Central",
                    "autocomplete": "off",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            dirigentes = list(self.instance.dirigentes.order_by("id")[:3])
            self._dirigentes_existentes = dirigentes
            for indice, dirigente in enumerate(dirigentes, start=1):
                self.initial[f"dirigente_{indice}"] = dirigente.nombre
                if dirigente.es_prioritario:
                    self.initial["dirigente_prioritario"] = str(indice)
                    self.initial["telefono_prioritario"] = dirigente.telefono
                    self.initial["correo_prioritario"] = dirigente.correo_electronico
        else:
            self._dirigentes_existentes = []

    def clean(self):
        cleaned_data = super().clean()
        prioritario = cleaned_data.get("dirigente_prioritario")
        nombre_prioritario = cleaned_data.get(f"dirigente_{prioritario}") if prioritario else None

        if prioritario and not nombre_prioritario:
            self.add_error(
                "dirigente_prioritario",
                "El dirigente elegido como prioritario debe tener un nombre.",
            )

        return cleaned_data

    def guardar_dirigentes(self, equipo):
        prioritario = self.cleaned_data["dirigente_prioritario"]
        existentes = getattr(self, "_dirigentes_existentes", [])

        for dirigente in existentes:
            if dirigente.es_prioritario:
                dirigente.es_prioritario = False
                dirigente.save(update_fields=["es_prioritario"])

        for indice, numero in enumerate(("1", "2", "3")):
            nombre = self.cleaned_data.get(f"dirigente_{numero}")
            if indice < len(existentes):
                dirigente = existentes[indice]
                if not nombre:
                    dirigente.delete()
                    continue
            elif nombre:
                dirigente = equipo.dirigentes.model(equipo=equipo)
            else:
                continue

            dirigente.nombre = nombre
            dirigente.es_prioritario = numero == prioritario
            dirigente.telefono = (
                self.cleaned_data["telefono_prioritario"]
                if dirigente.es_prioritario
                else ""
            )
            dirigente.correo_electronico = (
                self.cleaned_data["correo_prioritario"]
                if dirigente.es_prioritario
                else ""
            )
            dirigente.save()


class JugadorForm(forms.ModelForm):
    class Meta:
        model = Jugador
        fields = ["cedula", "nombres", "apellidos"]
        widgets = {
            "cedula": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-100",
                    "placeholder": "10 dígitos",
                    "inputmode": "numeric",
                    "autocomplete": "off",
                    "maxlength": 10,
                }
            ),
            "nombres": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-100",
                    "placeholder": "Nombres completos",
                    "autocomplete": "given-name",
                }
            ),
            "apellidos": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-100",
                    "placeholder": "Apellidos completos",
                    "autocomplete": "family-name",
                }
            ),
        }

    def clean_cedula(self):
        cedula = self.cleaned_data["cedula"].strip().replace(" ", "").replace("-", "")
        validar_cedula_ecuatoriana(cedula)
        if Jugador.objects.filter(cedula=cedula).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe un jugador registrado con esta cédula.")
        return cedula

    def clean(self):
        cleaned_data = super().clean()
        nombres = cleaned_data.get("nombres")
        apellidos = cleaned_data.get("apellidos")
        if nombres and apellidos:
            nombre_key = normalizar_nombre_completo(nombres, apellidos)
            if (
                Jugador.objects.filter(nombre_completo_key=nombre_key)
                .exclude(pk=self.instance.pk)
                .exists()
            ):
                raise forms.ValidationError(
                    "Ya existe un jugador registrado con estos nombres y apellidos."
                )
        return cleaned_data
