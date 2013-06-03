#/usr/bin/python
import threading, subprocess, datetime

import os, sys, time
sys.path.append('/home/ec2-user/nsr-django/nsr')
os.environ['DJANGO_SETTINGS_MODULE'] = 'nsr.settings'

from django.core.mail import send_mail
from dedool_jobs.models import Job
from status import check_job_status, get_elapsed_time

email_body = lambda name, id: \
"""
Hello,

Your file cleaning job, %s has completed! You can view your results here:
http://dedool.com/edit_results/%i/

Thank you,
The Dedool.com team
""" % (name, id)

def check_status():
	Job.objects.update()
	jobs = Job.objects.filter(status="running")
	print str(datetime.datetime.now()), jobs
	for job in jobs:
		status = check_job_status(job)
		print str(datetime.datetime.now()), job, status['status']
		if status['status'] == "COMPLETED" or status['status'] == "WAITING":
			job.finish_datetime = job.start_datetime + get_elapsed_time(job)
			job.set_status("results")
			job.save()
			
			if job.notify_by_email:
				send_mail("Dedool.com Job %s Complete!" % job.name, email_body(job.name, job.id), "support@nittanysystem.com", [job.user.email])
		time.sleep(20)

def repeat(event, action):
	while True:
		event.wait(300)
		action()

if __name__ == "__main__":
	event = threading.Event()
	t = threading.Thread(target=repeat, args=(event, check_status))
	t.start()