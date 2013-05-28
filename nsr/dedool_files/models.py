from django.db import models
from django.contrib.auth.models import User
from storages.backends.s3boto import S3BotoStorage
from django.core.urlresolvers import reverse

from dedool_jobs.models import Job
from cleancloud.constants import *

from boto.s3.key import Key
import boto

class UserFile(models.Model):
	"""
	A user-uploaded file in the file library. Files are stored in the USER_FILE_BUCKET Amazon S3 bucket, in folders by date of upload, with the username prefixed to the filename.
	
	type - type of file: 
					U - user uploaded
					C - cleaned
					S - sample datafile
	"""
	#1 user per file
	user = models.ForeignKey(User)
	#A file can be used in multiple jobs
	jobs = models.ManyToManyField(Job)
	input_file = models.FileField(upload_to='%Y/%m/%d', storage=S3BotoStorage(bucket=USER_FILE_BUCKET))
	size = models.IntegerField(max_length=100)
	rows = models.IntegerField(max_length=100)
	columns = models.IntegerField(max_length=100)
	type = models.CharField(max_length=1)
	public_link = models.CharField(default="", max_length=200)
	created = models.DateTimeField(auto_now_add=True)
	
	def __unicode__(self):
		return "-".join([str(self.user), self.type, str(self.input_file)])
	
	def add_job(self, job):
		self.jobs.add(job)
		self.save()
		
	def set_public_link(self):
		#make file publicly accessible
		c = boto.connect_s3()
		b = c.create_bucket(USER_FILE_BUCKET)
		k = Key(b)
		k.key = self.input_file.name
		k.set_acl('public-read')

		public_s3_file = "http://s3.amazonaws.com/" + USER_FILE_BUCKET + "/" + self.input_file.name
		self.public_link = public_s3_file
		self.save()
		return public_s3_file		
		
	def get_public_link(self):
		if self.public_link:
			return self.public_link
		else:
			self.set_public_link()
			return self.public_link
			
	def get_job(self):
		return self.jobs.get().id
		
	def get_job_name(self):
		return self.jobs.get().name
		
	def get_job_link(self):
		return reverse('dedool_functions.views.edit_results', args=(self.get_job(),))