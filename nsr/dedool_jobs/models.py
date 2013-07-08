from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.contrib.auth.models import User
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.core.mail import send_mail

from picklefield.fields import PickledObjectField


from cleancloud.constants import *
from cleancloud.s3ops import *
from dedool_functions.models import EditedResult

import re, boto, datetime, paramiko

class Job(models.Model):
	ALGORITHM_CHOICES = (('MH', 'MinHash'), ('NL', 'Nested Loop'))
	SIMILARITY_CHOICES = (('SoftTFIDF', 'SoftTFIDF'), ('Jaccard', 'Jaccard'), ('Level2JaroWinkler', 'Level2JaroWinkler'))
	NODE_SIZE_CHOICES = (('m1.small', 'Small'), ('m1.large', 'Large'))
	# status choices = uploaded, reviewed, running, post, results, generating
	
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
	value = models.CommaSeparatedIntegerField(max_length=50, default=[1])
	cost = models.IntegerField(default=0, validators=[MinValueValidator(0)])
	service = models.CharField(max_length=15, default="free")
	rows = models.IntegerField(default=0)
	jobflowid = models.CharField(max_length=50, default="")
	start_datetime = models.DateTimeField(null=True)
	finish_datetime = models.DateTimeField(null=True)
	notify_by_email = models.IntegerField(default=0)
	matched_rows = PickledObjectField(null=True, default='')
	
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
		
	def get_user_file(self):
		try:
			return self.userfile_set.all()[0]
		except IndexError:
			return ""
		
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
			
		name = str("".join(name.split("/")[-1]))
		
		return name
	
	def set_status(self, status):
		self.status = status
		self.save()

	def get_raw_results_data(job):
		return get_string_from_s3(DEDOOL_OUTPUT_BUCKET, "output/" + str(job.id) + "/" + job.get_output_file_name())
		
	def match_results_emr(job):
		results = job.get_raw_results_data()		
		results =  re.findall("(\d*)\t([\d,]*)", results)
		result_dict = {}
		all_values = {}
		delete = []
		
		for k, rstring in results:
			if k:
				result_dict[int(k)] = set(map(int, rstring.split(",")))
		
		for k1, value_set in result_dict.iteritems():
			for k2 in value_set:
				if k2 in result_dict and k2 not in delete:
					result_dict[k2] |= (value_set - set([k2]))
					result_dict[k2] |= set([k1])
					delete.append(k1)
				elif k2 in all_values and k1 not in delete:
					result_dict[all_values[k2]] |= value_set
					result_dict[all_values[k2]] |= set([k1])
					delete.append(k1)
				else:
					all_values[k2] = k1
		
		for k in delete:
			try:
				del result_dict[k]
			except KeyError:
				pass
		
		job.mark_secondary_rows_for_deletion(result_dict)
		
		return result_dict	
		
	def match_results_single(job):
		results = job.get_raw_results_data()
		results = re.findall("\((\d*),(\d*),(.*),(.*)\)", results)
		results = sorted([(int(id1), int(id2)) for (id1, id2, val1, val2) in results])
		result_dict = {}
		delete = []
		
		for id1, id2 in results:
			for k, result_set in result_dict.iteritems():
				if id1 in result_set or id1 == k:
					result_set.add(id2)
					break
				elif id2 in result_set or id2 == k:
					result_set.add(id1)
					break
			else:
				result_dict.setdefault(id1, set()).add(id2)
		
		for k, result_set in result_dict.iteritems():
			for k2, result_set2 in result_dict.iteritems():
				if k in result_set2:
					delete.append((k, k2))
		for k, k2 in delete:
			try:
				result_dict[k2].add(k)
				result_dict[k2] |= result_dict[k]
				del result_dict[k]
			except KeyError:
				pass
		
		job.mark_secondary_rows_for_deletion(result_dict)	
		
		return result_dict

	def get_matched_rows(self):
		if len(self.matched_rows) == 0:
			print "matched rows empty??"
			self.matched_rows = self.match_results_emr() if self.job_type == "e" else self.match_results_single()
			self.save()
		return self.matched_rows
		
	def mark_secondary_rows_for_deletion(job, results):
		for id1, result_set in results.iteritems():
			for id2 in result_set:
				if id1 != id2:
					job.mark_row_for_deletion(id2, True, force=False)
		
	def mark_row_for_deletion(job, row_id, checked, force=True):
		"""Mark row for deletion in the database."""
		# try:
		# 	result = EditedResult.objects.get(job=job, local_id=row_id)
		# 	if force:
		# 		result.value = checked
		# 		result.save()
		# except EditedResult.DoesNotExist:
		result = EditedResult(job=job, local_id=row_id, value=checked)
		result.save()					
	
	def finish_job(self):
		#set status first so subsequent job status checks won't trigger row matching again
		self.set_status("post")
		
		self.matched_rows = self.match_results_emr() if self.job_type == "e" else self.match_results_single()
		self.finish_datetime = self.start_datetime + self.get_elapsed_time()
		self.set_status("results")
		
		if self.notify_by_email:
			email_body = lambda name, id: \
"""
Hello,

Your file cleaning job, %s has completed! You can view your results here:
http://dedool.com/edit_results/%i/

Thank you,
The Dedool.com team
""" % (name, id)

			send_mail("Dedool.com Job %s Complete!" % self.name, email_body(self.name, self.id), "support@nittanysystem.com", [self.user.email])
		
		self.save()
		
	def get_elapsed_time(job):
		"""Get elapsed time for job."""
		if job.job_type == "e":
			return job.get_elapsed_time_emr(job.jobflowid)
		else:
			return datetime.timedelta(seconds=job.get_single_status())

	def get_elapsed_time_emr(job, emrid):
		"""Get elapsed time for EMR job with job flow id emrid, based on EMR job information."""
		emr = boto.connect_emr()
		jobflow = emr.describe_jobflow(emrid)
		emr.close()
	
		try:
			steps = [s for s in jobflow.steps if int(s.name.split("-")[1]) == job.id]
		except IndexError:
			try:
				stepcount = -2 if jobflow.steps[-1].name == "SimpleJoin" else -1
				starttime = datetime.datetime.strptime(jobflow.steps[stepcount].creationdatetime, '%Y-%m-%dT%H:%M:%SZ')
			except AttributeError as e:
				starttime = datetime.datetime.strptime(jobflow.startdatetime, '%Y-%m-%dT%H:%M:%SZ')
			except:
				starttime = datetime.datetime.strptime(jobflow.steps[-1].creationdatetime, '%Y-%m-%dT%H:%M:%SZ')
	
			try:
				endtime = datetime.datetime.strptime(jobflow.steps[-1].enddatetime, '%Y-%m-%dT%H:%M:%SZ')
			except AttributeError:
				endtime = datetime.datetime.today()	
			except:
				endtime = datetime.datetime.strptime(jobflow.steps[-1].enddatetime, '%Y-%m-%dT%H:%M:%SZ')
		else:
			starttime = datetime.datetime.strptime(steps[0].creationdatetime, '%Y-%m-%dT%H:%M:%SZ')
			endtime = datetime.datetime.strptime(steps[-1].enddatetime, '%Y-%m-%dT%H:%M:%SZ')

		return (endtime-starttime)		
		
	def get_single_status(job):
		"""Get the job status of single machine job job by reading the job status file on the single machine host."""
		client = paramiko.SSHClient()
		client.load_host_keys('/var/www/known_hosts')
		client.connect(SINGLE_MACHINE, 22, 'ec2-user', key_filename='/var/www/nsr-dev.pem')
		stdin, stdout, stderr = client.exec_command('cat ~/status-output/%s.log' % job.get_output_file_name())

		status = 0
		line = stdout.readline()

		try:
			status = float(line.strip())
		except ValueError as e:
			print e
			if "CANCELLED" in line:
				status = -1
			else:
				status = 0

		for line in stderr:
			print line.strip()

		return status		
	
	def __unicode__(self):
		return '-'.join([str(self.job_type), str(self.id), str(self.input_file), str(self.algorithm), str(self.similarity)])