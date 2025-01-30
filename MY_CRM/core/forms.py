from django import forms
from .models import Ticket, TicketStatus
from django.contrib.auth.models import User

class TicketForm(forms.ModelForm):
    assigned_to = forms.ModelChoiceField(queryset=User.objects.all(), required=False, label="Назначить сотрудника")

    class Meta:
        model = Ticket
        fields = ['client_name', 'account_number', 'phone_number', 'description', 'assigned_to'] 

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.instance.status = TicketStatus.objects.get(id=1)
