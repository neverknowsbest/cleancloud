from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.template import RequestContext
from django.core.files import File
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q

from cleancloud.models import *
from cleancloud.forms import *

from util import *
from status import *

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
			return redirect('cleancloud.views.select', job.id)
	else:		
		#Get user jobs to display "Current Jobs" table
		active_jobs = get_active_jobs(request.user)
		all_user_jobs = Job.objects.filter(user=request.user)
		
		default_name = "-".join([request.user.username, str(len(all_user_jobs))])
	
	return render(request, 'cleancloud/start.html', {'active':active_jobs, 'default_name':default_name})

@login_required
def continue_job(request, job_id):
	"""Redirect to the current step of the given job."""
	job = Job.objects.get(id=job_id)
	
	r = get_redirect_from_job_status(job)
	return r

@login_required
def upload(request, job_id):
	"""Django view for the file upload page"""
	job = get_job_or_error(job_id, 'cleancloud.views.upload')
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
					
			return redirect('cleancloud.views.review', job.id)
	else:
		form = FileUploadForm()
	
	return render(request, 'cleancloud/upload.html', {'form':form})

@login_required
def select(request, job_id):
	"""Select file for job using file manager."""
	job = get_job_or_error(job_id, 'cleancloud.views.upload')
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

			return redirect('cleancloud.views.review', job.id)
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
		error = "Requested job id does not exist. Please try your file upload again by clicking <a href='%s'>here</a>." % reverse('cleancloud.views.upload')
		return render(request, 'cleancloud/review.html', {'error':error})
	else:
		error = check_job_submitted(job)
		if error:
			return render(request, 'cleancloud/review.html', {'error':error, 'job':job})
				
	if request.method == "POST":
		form = ReviewForm(request.POST['ncols'], request.POST)
		print form.errors
		if form.is_valid():
			job.key = form.cleaned_data['key']
			job.value = ",".join(form.cleaned_data['value'])
			job.rows = form.cleaned_data['nrows']
			job.threshold = form.cleaned_data['threshold']
			print job.threshold, form.cleaned_data['threshold']
			prepare_data(job)
			job.set_status("reviewed")
			job.save()

			return redirect('cleancloud.views.configure', job.id)
	else:
		table_header, table_body, n, ncols = get_preview(job)
		
	return render(request, 'cleancloud/review.html', {'job':job, 'n':n, 'table_header':table_header, 'table_body':table_body, 'ncols':ncols, 'nrows':n})	

@login_required
def configure(request, job_id):
	"""Django view for the configure job page"""
	try:
		job = Job.objects.get(id=job_id)
	except:
		error = "Requested job id does not exist. Please try your file upload again by clicking <a href='%s'>here</a>." % reverse('cleancloud.views.upload')
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
			job.set_status("running")
			job.jobflowid = jobflowid
			job.start_datetime = datetime.datetime.now()
			job.save()

			return redirect('cleancloud.views.status', job.id)
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
		return render(request, 'cleancloud/run.html', {'error':error})

	if request.method == "POST":
		form = ResultsForm(request.POST)
		
		if form.is_valid():
			job.set_status("completed")
			job.save()
			save_results(job, eval(form.cleaned_data['delete']), request.user)
		
			return HttpResponseRedirect(reverse('cleancloud.views.results', args=(str(job.id),)))
	
	return render(request, 'cleancloud/status.html', {'job':job})

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
		return redirect('cleancloud.views.status', job.id)	
	
	return render(request, 'cleancloud/status_form.html')

@login_required
def profile(request):
	try:
		profile = request.user.userprofile
	except UserProfile.DoesNotExist:
		profile = None
		
	return render(request, 'cleancloud/profile.html', {'profile':profile})

@login_required
def edit_profile(request):
	"""Edit or add auxiliary account information such as name, address, etc. This data goes into the UserProfile model, not the User model, which is only for authentication."""
	try:
		profile = request.user.userprofile
	except UserProfile.DoesNotExist:
		profile = None

	if request.method == "POST":
		if not profile:
			form = UserProfileForm(request.POST)
		form = UserProfileForm(request.POST, instance=profile)

		if form.is_valid():
			form.save()
			return redirect('cleancloud.views.profile')
		else:
			return render(request, 'cleancloud/edit_profile.html', {'profile':profile, 'error':form.errors})
	
	return render(request, 'cleancloud/edit_profile.html', {'profile':profile})
	
@login_required
def job_history(request):
	"""Display current user's job history."""
	finished_jobs = Job.objects.filter((Q(status="completed") | Q(status="results") | Q(status="cancelled")), user=request.user)
	active_jobs = get_active_jobs(request.user)
	
	return render(request, 'cleancloud/job_history.html', {'active':active_jobs, 'finished':finished_jobs})
	
@login_required
def functions(request):
	"""Display available data cleaning functionality to user."""
	return render(request, 'cleancloud/functions.html')
	

	