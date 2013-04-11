from django import forms
from models import *

class FileUploadForm(forms.Form):
	uploaded_file = forms.FileField(required=False)
	sample = forms.FilePathField(path='/var/www/sample', required=False)
	urgency = forms.ChoiceField(required=False, choices=[('High', 'High'), ('Low', 'Low')])
	
class ReviewForm(forms.Form):
	key = forms.IntegerField()
	threshold = forms.FloatField()
	nrows = forms.IntegerField()

	def __init__(self, n, *args, **kwargs):
		super(ReviewForm, self).__init__(*args, **kwargs)
		self.fields["value"] = forms.MultipleChoiceField(choices=[(str(i), str(i)) for i in range(int(n))])
		
class ServiceLevelForm(forms.Form):
	service = forms.CharField()

class ResultsForm(forms.Form):
	delete = forms.CharField()
	
class StartJobForm(forms.Form):
	name = forms.CharField(label="Job Name")	
	
class SelectFileForm(forms.Form):
	file = forms.CharField()	
	
class JobForm(forms.ModelForm):
	class Meta:
		model = Job
		exclude = ('status', 'job_type', 'input_file', 'user', 'cost', 'value')

class UserProfileForm(forms.ModelForm):
	class Meta:
		model = UserProfile
		exclude = ('jobs', 'user', 'street_address_2')
