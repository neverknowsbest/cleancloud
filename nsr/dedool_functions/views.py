from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.core.files import File
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q

from cleancloud.models import *
from cleancloud.forms import *

from cleancloud.util import *
from cleancloud.status import *

import os, datetime, magic

@login_required
def start(request):
	"""Django view for the start cleaning job page. 
	
	-If logged-in user has an active job, display it, and do not allow user to create a new job
	-Create a new job in the database when user clicks "Start New Job."
	-Associate this job with the logged-in user as the "active" job
	
	"""
	#if form has been submitted
	if request.method == 'POST':
		form = StartJobForm(request.POST)

		if form.is_valid():
			job = Job(user=request.user, name=form.cleaned_data['name'])
			job.save()
			return redirect('dedool_functions.views.select', job.id)
	else:		
		#Get user jobs to display "Current Jobs" table
		active_jobs = get_active_jobs(request.user)
		all_user_jobs = Job.objects.filter(user=request.user)
		
		default_name = "-".join([request.user.username, str(len(all_user_jobs))])
	
	return render(request, 'cleancloud/start.html', {'active':active_jobs, 'default_name':default_name})
	
@login_required
def upload(request, job_id):
	"""Django view for the file upload page"""
	job = get_job_or_error(job_id, 'dedool_functions.views.upload')
	if not isinstance(job, Job):
		return render(request, 'cleancloud/upload.html', {'error':error})
		
	if request.method == 'POST':
		request.POST['sample'] = get_sample_filename(request.POST['sample'])
		form = FileUploadForm(request.POST, request.FILES)

		if form.is_valid():
			if form.cleaned_data['sample'] == "/var/www/sample/none.txt":
				filename = "%s_%s" % (job.id, request.FILES['uploaded_file'].name)
				file_data = request.FILES['uploaded_file']
				job.input_file.save(filename, file_data)
				job.save()
			else:
				filename = "%s_%s" % (job.id, os.path.basename(form.cleaned_data['sample']))
				with open(form.cleaned_data['sample']) as f:
					file_data = File(f)
					job.input_file.save(filename, file_data)
					job.set_status("uploaded")
					job.save()
					
			return redirect('dedool_functions.views.review', job.id)
	else:
		form = FileUploadForm()
	
	return render(request, 'cleancloud/upload.html', {'form':form})
	
@login_required
def select(request, job_id):
	"""Select file for job using file manager."""
	job = get_job_or_error(job_id, 'dedool_functions.views.upload')
	if not isinstance(job, Job):
		return render(request, 'cleancloud/select.html', {'error':job})
	error = None
	
	if request.method == "POST":
		form = SelectFileForm(request.POST)
		
		if form.is_valid():
			try:
				uf = UserFile.objects.get(id=form.cleaned_data['file'])
			except DoesNotExist:
				error = "Selected user file does not exist. Please contact an administrator."
				return render(request, 'cleancloud/select.html', {'error':error})
			
			job.add_file(uf)

			return redirect('dedool_functions.views.review', job.id)
		else:
			error = "Please select a file."
	
	files = get_user_file_library(request.user, "select")
	sample_files = get_sample_file_library()
	
	return render(request, 'cleancloud/select.html', {'files':files, 'sample_files':sample_files, 'error':error})
	
@login_required
def review(request, job_id):
	"""Django view for the review data page"""
	try:
		job = Job.objects.get(id=job_id)
	except:
		error = "Requested job id does not exist. Please try your file upload again by clicking <a href='%s'>here</a>." % reverse('dedool_functions.views.upload')
		return render(request, 'cleancloud/review.html', {'error':error})
	else:
		error = check_job_submitted(job)
		if error:
			return render(request, 'cleancloud/review.html', {'error':error, 'job':job})
				
	if request.method == "POST":
		form = ReviewForm(request.POST['ncols'], request.POST)

		if form.is_valid():
			job.key = form.cleaned_data['key']
			job.value = ",".join(form.cleaned_data['value'])
			job.rows = form.cleaned_data['nrows']
			job.threshold = form.cleaned_data['threshold']
			
			prepare_data(job)
			job.set_status("reviewed")
			job.save()

			return redirect('dedool_functions.views.configure', job.id)
		else:
			error = []
			if 'value' not in request.POST or len(request.POST['value']) == 0:
				error.append("You must select a column to be used in matching.")
			
			error = '\n'.join(error)
	table_header, table_body, n, ncols = get_preview(job)
		
	return render(request, 'cleancloud/review.html', {'job':job, 'table_header':table_header, 'table_body':table_body, 'ncols':ncols, 'nrows':n, 'error':error})	

@login_required
def configure(request, job_id):
	"""Django view for the configure job page"""
	try:
		job = Job.objects.get(id=job_id)
	except:
		error = "Requested job id does not exist. Please try your file upload again by clicking <a href='%s'>here</a>." % reverse('dedool_functions.views.upload')
		return render(request, 'cleancloud/configure.html', {'error':error})
	else:
		error = check_job_submitted(job)
		if error:
			return render(request, 'cleancloud/configure.html', {'error':error, 'job':job})
	
	if request.method == "POST":
		form = ServiceLevelForm(request.POST)

		if form.is_valid():
			fill_job_from_service(job, form.cleaned_data['service'])
			
			jobflowid = run_job(job)
			job.notify_by_email = int(form.cleaned_data['notify'])
			job.set_status("running")
			job.jobflowid = jobflowid
			job.start_datetime = datetime.datetime.now()
			job.save()

			return redirect('dedool_functions.views.status', job.id)
	else:
		tiers = get_tiers(job)
		
	return render(request, 'cleancloud/configure.html', {'job':job, 'tiers':tiers})

@login_required
def status(request, job_id):
	"""Django view for the job status page (loads ajax to check job status)"""
	try:
		job = Job.objects.get(id=job_id)
	except:
		error = "Requested job id does not exist."
		return render(request, 'cleancloud/status.html', {'error':error})
	
	return render(request, 'cleancloud/status.html', {'job':job})

@login_required
def edit_results(request, job_id):
	"""Django view for editing results."""
	try:
		job = Job.objects.get(id=job_id)
	except:
		error = "Requested job id does not exist."
		return render(request, 'cleancloud/edit.html', {'error':error})

	if request.method == "POST":
		# job.set_status("completed")
		# job.save()
		save_results(job, request.user)
		
		return HttpResponseRedirect(reverse('dedool_functions.views.results', args=(str(job.id),)))

	mark_secondary_rows_for_deletion(job)
	value_columns = [int(v)-1 for v in job.value.strip("[]").split(",")]
	ncols = job.get_user_file().columns
	rows = get_results_table_rows(job, 0, 5)
	
	return render(request, 'cleancloud/edit.html', {'job':job, 'ncols':range(ncols), 'values':value_columns, 'empty':rows == 0})

@login_required
def results(request, job_id):
	"""Django view for the final results"""
	try:
		job = Job.objects.get(id=job_id)
	except:
		error = "Requested job id does not exist."
		return render(request, 'cleancloud/results.html', {'error':error})		
	
	#Get and format results for display
	results_link = get_public_results_link(job)
	results_table = get_final_results_table(job)

	return render(request, 'cleancloud/results.html', {'results_link':results_link, 'results_table':results_table})		

@login_required
def status_form(request):	
	if request.method == "POST":
		try:
			job_id = int(request.POST['jobid'])
			job = Job.objects.get(id=job_id)
		except:
			error = "Requested job id does not exist."
			return render(request, 'cleancloud/status_form.html', {'error':error})
		return redirect('dedool_functions.views.status', job.id)	
	
	return render(request, 'cleancloud/status_form.html')