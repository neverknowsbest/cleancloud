from django import forms
from models import *

class FileUploadForm(forms.Form):
	uploaded_file = forms.FileField(required=False)
	sample = forms.FilePathField(path='/var/www/sample', required=False)
	urgency = forms.ChoiceField(required=False, choices=[('High', 'High'), ('Low', 'Low')])
	
class ReviewForm(forms.Form):
	key = forms.IntegerField()
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
		
class UserFileForm(forms.ModelForm):	
	def save(self, user, commit=True):
		filename = "%s_%s" % (user.username, self.files['input_file'].name)		
		instance = forms.ModelForm.save(self, commit=False)
		instance.input_file.name = filename
		instance.user = user
		instance.size = self.files['input_file'].size
		instance.rows, instance.columns = self.get_file_info(instance.input_file)
		instance.type = "U"
		
		if commit:
			instance.save()

		return instance
		
	def get_file_info(self, input_file):
		lines = input_file.readlines()
		input_file.seek(0)
		rows = len(lines)
		columns = len(lines[0].split("\t" if "\t" in lines[0] else ","))
		return rows, columns
		
	class Meta:
		model = UserFile
		exclude = ('user', 'jobs', 'size', 'rows', 'columns', 'type')