from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from dedool_jobs.models import Job

from cleancloud.util import *
from cleancloud.status import *

@login_required
def continue_job(request, job_id):
	"""Redirect to the current step of the given job."""
	job = Job.objects.get(id=job_id)
	
	r = get_redirect_from_job_status(job)
	return r

@login_required
def job_history(request):
	"""Display current user's job history."""
	finished_jobs = Job.objects.filter((Q(status="completed") | Q(status="results") | Q(status="cancelled")), user=request.user)
	active_jobs = get_active_jobs(request.user)
	
	return render(request, 'cleancloud/job_history.html', {'active':active_jobs, 'finished':finished_jobs})