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
def continue_job(request, job_id):
	"""Redirect to the current step of the given job."""
	job = Job.objects.get(id=job_id)
	
	r = get_redirect_from_job_status(job)
	return r

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
	

	