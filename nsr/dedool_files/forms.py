from django import forms

from dedool_files.models import UserFile

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
		exclude = ('user', 'jobs', 'size', 'rows', 'columns', 'type', 'public_link')