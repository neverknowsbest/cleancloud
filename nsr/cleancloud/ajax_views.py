from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

from cleancloud.models import *
from cleancloud.forms import *

from util import *
from status import *

@login_required
def check(request, job_id):
	"""Django view for result-checking ajax request (not exposed to user)"""
	job = Job.objects.get(id=job_id)

	if request.is_ajax() or \
	(request.user.is_authenticated() and \
	request.user == job.user):
		status = check_job_status(job)
		return HttpResponse(status, mimetype="application/json")

@login_required
def remove(request, file_id):
	"""Remove a user file."""
	user_file = UserFile.objects.get(id=file_id)
	success = remove_user_file(user_file)
	user_file.delete()

	return HttpResponse(success)
	
@login_required
def hide(request, job_id):
	"""Hide a job from the inactive job history table."""
	try:
		job = Job.objects.get(id=job_id)
	except:
		return HttpResponse("Invalid job specified.")
	
	job.set_status("hidden")
	
	return HttpResponse("Success.")
	
@login_required
def cancel(request, job_id):
	try:
		job = Job.objects.get(id=job_id)
	except:
		error = "Requested job id does not exist."
		return render(request, 'cleancloud/results.html', {'error':error})
	
	cancel_job(job)
	job.cancel()
	
	return HttpResponse(job.status)	
	
@login_required
def edit(request, job_id):
	"""Save edited data from results page."""
	try:
		job = Job.objects.get(id=job_id)
	except:
		return HttpResponse("Invalid job specified.")
	
	save_edits(job, request)

	return HttpResponse("Changes saved.")

@login_required
def revert(request, job_id, input_id):
	"""Get the original data for jobid, at input_id (<row id>-<column id>)"""
	try:
		job = Job.objects.get(id=job_id)
	except:
		return HttpResponse("Invalid job specified.")

	data_json = get_original_data(job, input_id)
	
	return HttpResponse(data_json, mimetype="application/json")	