from django import forms

from dedool_profile.models import UserProfile


class UserProfileForm(forms.ModelForm):
    error_css_class = 'errorField'

    class Meta:
        model = UserProfile
        fields = ('first_name', 'last_name', 'company', 'phone', 'street_address_1',
                  'street_address_2', 'city', 'state', 'zipcode', )
