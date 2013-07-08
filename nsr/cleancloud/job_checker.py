#/usr/bin/python
import threading, subprocess, datetime

import os, sys, time
sys.path.append('/home/ec2-user/nsr-django/nsr')
os.environ['DJANGO_SETTINGS_MODULE'] = 'nsr.settings'

from dedool_jobs.models import Job
from status import check_job_status

def check_status():
	Job.objects.update()
	jobs = Job.objects.filter(status="running")
	print str(datetime.datetime.now()), jobs
	for job in jobs:
		status = check_job_status(job)
		print str(datetime.datetime.now()), job, status['status']
		if status['status'] == "COMPLETED" or (status['status'] == "WAITING" and job.status != "results" and job.status != "post"):
			job.finish_job()

		time.sleep(20)

def repeat(event, action):
	while True:
		event.wait(300)
		action()

if __name__ == "__main__":
	event = threading.Event()
	t = threading.Thread(target=repeat, args=(event, check_status))
	t.start()