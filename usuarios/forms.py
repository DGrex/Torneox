from django.contrib.auth.forms import AuthenticationForm


class TorneoXAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm "
            "focus:border-emerald-600 focus:outline-none focus:ring-2 "
            "focus:ring-emerald-100"
        )
        self.fields["username"].widget.attrs.update(
            {"class": input_class, "autocomplete": "username"}
        )
        self.fields["password"].widget.attrs.update(
            {"class": input_class, "autocomplete": "current-password"}
        )
