from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.contrib.auth.models import User
from django.contrib.auth.models import User
from django.db.models.signals import post_save

from cleancloud.constants import *

class Job(models.Model):
	ALGORITHM_CHOICES = (('MH', 'MinHash'), ('NL', 'Nested Loop'))
	SIMILARITY_CHOICES = (('SoftTFIDF', 'SoftTFIDF'), ('Jaccard', 'Jaccard'), ('Level2JaroWinkler', 'Level2JaroWinkler'))
	NODE_SIZE_CHOICES = (('m1.small', 'Small'), ('m1.large', 'Large'))
	# status choices = uploaded, reviewed, running, results
	
	#1 user per job
	user = models.ForeignKey(User)
	# user file interface files accessible through job.userfile_set.all()
	input_file = models.FileField(upload_to='input/%Y/%m/%d') #deprecated, may be removed in future database model
	name = models.CharField(max_length=100, default="")
	algorithm = models.CharField(max_length=2, default="MH", choices=ALGORITHM_CHOICES)
	similarity = models.CharField(max_length=20, default="Jaccard", choices=SIMILARITY_CHOICES)
	threshold = models.FloatField(default=0.9)
	hashes = models.IntegerField(default=3, validators=[MaxValueValidator(8), MinValueValidator(3)])
	nodes = models.IntegerField(null=True, blank=True, default=4, validators=[MaxValueValidator(8), MinValueValidator(4)])
	node_size = models.CharField(blank=True, max_length=10, default="m1.small", choices=NODE_SIZE_CHOICES)
	job_type = models.CharField(null=True, max_length=1, default="e")
	#possible states: unsubmitted, uploaded, reviewed, running, results, completed, cancelled
	status = models.CharField(max_length=20, default="unsubmitted")
	key = models.IntegerField(default=0)
	value = models.CommaSeparatedIntegerField(max_length=5, default=[1])
	cost = models.IntegerField(default=0, validators=[MinValueValidator(0)])
	service = models.CharField(max_length=15, default="free")
	rows = models.IntegerField(default=0)
	jobflowid = models.CharField(max_length=50, default="")
	start_datetime = models.DateTimeField(null=True)
	finish_datetime = models.DateTimeField(null=True)
	
	def cancel(self):
		self.status = "cancelled"
		self.save()
	
	def clear_userfile_set(self):
		self.userfile_set.clear()
		
	def get_s3_input_path(self):
		try:
			return "s3n://cleancloud/" + self.userfile_set.all()[0].input_file.name
		except IndexError:
			return ""
	
	def get_output_file_name(self):
		return self.get_input_file().name.split("/")[-1]
	
	def get_s3_output_path(self):
		return "s3n://cleancloud/output/%i/%s" % (self.id, self.get_output_file_name())
	
	def get_input_file(self):
		try:
			return self.userfile_set.all()[0].input_file
		except IndexError:
			return ""
			
	def add_file(self, uf):
		self.clear_userfile_set()
		uf.add_job(self)
		self.rows = uf.rows
		self.status = "uploaded"
		self.save()
		
	def get_short_input_file_name(self):
		try:
			name = self.userfile_set.all()[0].input_file.name
		except:
			return ""
			
		if "_" in name:
			name = str("".join(name.split("/")[-1].split("_")[1:]))	
		else:
			name = str("".join(name.split("/")[-1]))
		return name			
	
	def set_status(self, status):
		self.status = status
		self.save()
	
	def __unicode__(self):
		return '-'.join([str(self.job_type), str(self.id), str(self.input_file), str(self.algorithm), str(self.similarity)])