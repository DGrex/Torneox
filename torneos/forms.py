from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory

from .models import Encuentro, Jornada, Torneo


class TorneoForm(forms.ModelForm):
    class Meta:
        model = Torneo
        fields = [
            "nombre",
            "equipos_participantes",
            "equipos_clasificados",
            "jugadores_maximos_por_equipo",
            "bonificacion_habilitada",
        ]
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-100",
                    "placeholder": "Ej. Campeonato de Apertura",
                    "autocomplete": "off",
                }
            ),
            "equipos_clasificados": forms.NumberInput(
                attrs={
                    "class": "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-100",
                    "min": 1,
                    "step": 1,
                    "placeholder": "Escribe la cantidad",
                }
            ),
            "equipos_participantes": forms.NumberInput(
                attrs={
                    "class": "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-100",
                    "min": 1,
                    "step": 1,
                    "placeholder": "Escribe la cantidad",
                }
            ),
            "jugadores_maximos_por_equipo": forms.NumberInput(
                attrs={
                    "class": "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-100",
                    "min": 1,
                    "step": 1,
                    "placeholder": "Escribe la cantidad",
                }
            ),
            "bonificacion_habilitada": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 rounded border-slate-300 text-emerald-700 focus:ring-emerald-600"
                }
            ),
        }

    def clean_equipos_participantes(self):
        cantidad = self.cleaned_data.get("equipos_participantes")
        if cantidad is not None and cantidad % 2:
            raise ValidationError("La cantidad de participantes debe ser par.")
        return cantidad


class FechaJornadaForm(forms.ModelForm):
    class Meta:
        model = Jornada
        fields = ["fecha_programada"]
        widgets = {
            "fecha_programada": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "rounded-lg border border-slate-300 px-3 py-2 text-sm",
                }
            )
        }


class ResultadoEncuentroForm(forms.ModelForm):
    class Meta:
        model = Encuentro
        fields = ["goles_local", "goles_visitante"]
        widgets = {
            "goles_local": forms.NumberInput(
                attrs={"min": 0, "class": "w-20 rounded-lg border border-slate-300 px-2 py-2 text-center"}
            ),
            "goles_visitante": forms.NumberInput(
                attrs={"min": 0, "class": "w-20 rounded-lg border border-slate-300 px-2 py-2 text-center"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["goles_local"].required = True
        self.fields["goles_visitante"].required = True


class PartidoJornadaForm(forms.Form):
    equipo_local = forms.ModelChoiceField(
        queryset=None,
        label="Local",
        widget=forms.Select(
            attrs={"class": "w-full rounded-lg border border-slate-300 px-2 py-2 text-sm"}
        ),
    )
    equipo_visitante = forms.ModelChoiceField(
        queryset=None,
        label="Visitante",
        widget=forms.Select(
            attrs={"class": "w-full rounded-lg border border-slate-300 px-2 py-2 text-sm"}
        ),
    )

    def __init__(self, *args, equipos, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["equipo_local"].queryset = equipos
        self.fields["equipo_visitante"].queryset = equipos

    def clean(self):
        cleaned_data = super().clean()
        local = cleaned_data.get("equipo_local")
        visitante = cleaned_data.get("equipo_visitante")
        if local and visitante and local.pk == visitante.pk:
            raise ValidationError("Un partido necesita dos equipos distintos.")
        return cleaned_data


def jornada_historica_formset(torneo, *args, **kwargs):
    equipos = torneo.equipos.order_by("nombre")

    class FormularioPartido(PartidoJornadaForm):
        def __init__(self, *form_args, **form_kwargs):
            super().__init__(*form_args, equipos=equipos, **form_kwargs)

    return formset_factory(
        FormularioPartido,
        extra=equipos.count() // 2,
        min_num=equipos.count() // 2,
        max_num=equipos.count() // 2,
        validate_min=True,
        validate_max=True,
    )(*args, **kwargs)
