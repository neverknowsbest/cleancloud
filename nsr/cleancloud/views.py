from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail

from cleancloud.models import *
from cleancloud.forms import *
	
def contact(request):
	if request.method == "POST":
		send_mail("Dedool.com feedback from %s" % request.POST["name"], "\n".join([request.POST["comment"], request.POST["mail"]]), "support@nittanysystem.com", ["support@nittanysystem.com"], fail_silently=False)
		
		return render(request, "cleancloud/contact.html", {"submitted":True})
		
	return render(request, "cleancloud/contact.html")