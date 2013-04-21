import floppyforms as forms

from dedool_profile.models import UserProfile


class UserProfileForm(forms.ModelForm):

    class Meta:
        model = UserProfile
        fields = ('first_name', 'last_name', 'company', 'phone', 'street_address_1',
                  'street_address_2', 'city', 'state', 'zipcode', )
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Last Name'}),
            'company': forms.TextInput(attrs={'placeholder': 'Company'}),
            'phone': forms.PhoneNumberInput(attrs={'placeholder': 'Phone Number', 'pattern': '\d{10}'}),
            'street_address_1': forms.TextInput(attrs={'placeholder': 'Street Addres 1'}),
            'street_address_2': forms.TextInput(attrs={'placeholder': 'Street Addres 2'}),
            'city': forms.TextInput(attrs={'placeholder': 'City'}),
            'state': forms.TextInput(attrs={'placeholder': 'State'}),
            'zipcode': forms.TextInput(attrs={'placeholder': 'Zip Code', 'pattern': '\d{5}'}),
        }
