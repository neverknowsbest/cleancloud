from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.contrib.auth.models import User
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from storages.backends.s3boto import S3BotoStorage

class Job(models.Model):
	ALGORITHM_CHOICES = (('MH', 'MinHash'), ('NL', 'Nested Loop'))
	SIMILARITY_CHOICES = (('SoftTFIDF', 'SoftTFIDF'), ('Jaccard', 'Jaccard'), ('Level2JaroWinkler', 'Level2JaroWinkler'))
	NODE_SIZE_CHOICES = (('m1.small', 'Small'), ('m1.large', 'Large'))
	# status choices = uploaded, reviewed, running, results
	
	#1 user per job
	user = models.ForeignKey(User)
	# user file interface files accessible through job.userfile_set.all()
	input_file = models.FileField(upload_to='input/%Y/%m/%d')	#deprecated, may be removed in future database model
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
				
	def get_s3_output_path(self):
		return "s3n://cleancloud/output/%i/%s" % (self.id, self.get_input_file().name)
		
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

class UserProfile(models.Model):  
	#A user profile can have many jobs
	jobs = models.ManyToManyField(Job)
	#1 profile per user, 1 user per profile	
	user = models.OneToOneField(User)
	first_name = models.CharField(max_length=100, default="")
	last_name = models.CharField(max_length=100, default="")
	street_address_1 = models.CharField(max_length=100, default="")
	street_address_2 = models.CharField(max_length=100, default="")
	city = models.CharField(max_length=100, default="")
	state = models.CharField(max_length=100, default="")
	zipcode = models.IntegerField(max_length=5, default=0)
	
	def __unicode__(self):  
		return "%s's profile %s" % (self.user, self.first_name)

class EditedResult(models.Model):
	job = models.ForeignKey(Job)
	local_id = models.CharField(max_length=31)
	value = models.TextField()
	
	def __unicode__(self):
		return '-'.join([str(self.job.id), str(self.local_id), self.value])

class UserFile(models.Model):
	#1 user per file
	user = models.ForeignKey(User)
	#A file can be used in multiple jobs
	jobs = models.ManyToManyField(Job)
	input_file = models.FileField(upload_to='%Y/%m/%d', storage=S3BotoStorage(bucket="dedool-user-files"))
	size = models.IntegerField(max_length=100)
	rows = models.IntegerField(max_length=100)
	columns = models.IntegerField(max_length=100)
	type = models.CharField(max_length=1)
	
	def __unicode__(self):
		return "-".join([str(self.user), self.type, str(self.input_file)])
	
	def add_job(self, job):
		self.jobs.add(job)
		self.save()
	
#Automatically create user profile and connect it to the User when a new User is created
def create_user_profile(sender, instance, created, **kwargs):  
	if created:  
		profile, created = UserProfile.objects.get_or_create(user=instance)  
post_save.connect(create_user_profile, sender=User) 		