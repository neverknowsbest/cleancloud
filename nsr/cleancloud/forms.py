from django import forms
from django.core.validators import MaxLengthValidator
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
		self.fields["value"] = forms.MultipleChoiceField(choices=[(str(i), str(i)) for i in range(int(n))], validators=[MaxLengthValidator(50)])
		
class ServiceLevelForm(forms.Form):
	service = forms.CharField()
	notify = forms.BooleanField(required=False)

class ResultsForm(forms.Form):
	delete = forms.CharField()
	
class StartJobForm(forms.Form):
	name = forms.CharField(label="Job Name")	
	
class SelectFileForm(forms.Form):
	file = forms.CharField()

