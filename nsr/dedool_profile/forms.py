from django import forms
from dedool_profile.models import UserProfile

class UserProfileForm(forms.ModelForm):
	class Meta:
		model = UserProfile
		exclude = ('jobs', 'user', 'street_address_2')
