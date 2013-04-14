from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q

from dedool_jobs.models import Job
from dedool_profile.models import UserProfile
from dedool_profile.forms import UserProfileForm

from cleancloud.util import *
from cleancloud.status import *

@login_required
def profile(request):
	try:
		profile = request.user.userprofile
	except UserProfile.DoesNotExist:
		profile = None

	return render(request, 'cleancloud/profile.html', {'profile':profile})

@login_required
def edit_profile(request):
	"""
	Edit or add auxiliary account information such as name, address, etc. This data goes into the
	UserProfile model, not the User model, which is only for authentication.
	"""
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
			return redirect('dedool_profile.views.profile')
		else:
			return render(request, 'cleancloud/edit_profile.html', {'profile':profile, 'error':form.errors})

	return render(request, 'cleancloud/edit_profile.html', {'profile':profile})
