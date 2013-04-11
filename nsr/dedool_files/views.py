from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from cleancloud.models import *
from dedool_files.forms import *

from cleancloud.util import *
from cleancloud.status import *
from cleancloud.constants import *

@login_required
def files(request):
	"""Display user file management system."""
	error = ""
	files = get_user_file_library(request.user, "files") 
	total_size = sum(f[0].size for f in files)
	percentage = "%0.2f" % (total_size/QUOTA)
	
	if request.method == "POST":
		form = UserFileForm(request.POST, request.FILES)
		
		if form.is_valid():
			if not user_file_is_unique(request.user, request.FILES['input_file'].name):
				error += "A file with this name already exists. Please select another file, rename this file, or remove the existing file.\n"	
		 	if request.FILES['input_file'].content_type != "text/csv":
				error += "File is not a CSV file. Please upload a comma-separated value file.\n"
			if total_size + request.FILES['input_file'].size > QUOTA:
				error += "Maximum storage quota reached. Please remove some files and try again.\n"
			if request.FILES['input_file'].size == 0:
				error += "Empty file uploaded. Please upload a file with size greater than 0. \n"
			
			if not error:
				form.save(request.user)
				return redirect('dedool_files.views.files')
		else:
			error = form.errors
	form = UserFileForm()
		
	return render(request, 'cleancloud/files.html', {"files":files, "form":form, "error":error, 'total_size':total_size, 'quota':QUOTA, 'percentage':percentage})

