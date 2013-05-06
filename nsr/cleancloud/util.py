import boto, json, subprocess, sys, re, pickle, paramiko, datetime
from boto.emr.step import JarStep
from django.shortcuts import redirect
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.contrib.auth.models import User

from cleancloud.constants import *
from dedool_jobs.models import Job
from dedool_files.models import UserFile
from dedool_functions.models import EditedResult
from cleancloud.status import match_results

def get_job_or_error(job_id, page):
	"""Get job by job_id, or return an error"""
	try:
		job = Job.objects.get(id=job_id)
	except:
		error = "Requested job id does not exist. Please try your file upload again by clicking <a href='%s'>here</a>." % reverse(page, args=(job_id,))
		return error
	else:
		error = check_job_submitted(job)
		if error:
			print error
			return error
		return job

def get_sample_filename(sample):
	"""Translate sample filename choice into the actual filename"""
	if sample == "Test Run Using Restaurant Input":
		local_filename = "/var/www/sample/sample-input-restaurant.csv"
	elif sample == "SecondString Restaurant Input (864 records)":
		local_filename = "/var/www/sample/sample-input-restaurant.csv"
	elif sample == "DBgen Synthetic Input (3973 records)":
		local_filename = "/var/www/sample/sample-input-dbgen.csv"
	elif sample == "None":
		local_filename = "/var/www/sample/none.txt"
	else:
		local_filename = "/var/www/sample/%s.txt" % sample.split()[0]
	return local_filename
	
def get_preview(job, n=10):
	"""Get the 10 line preview of the data file for the configure page"""
	lines = []
	for i, line in enumerate(job.get_input_file()):
		marker = '\t' if '\t' in line else ','
		if i < n:
			lines.append(marker.join([str(i+1), line]))
		if i == n:
			break
			
	return format_preview(job, lines, job.rows)

def format_preview(job, lines, linecount):
	"""Format the <linecount> line preview for the configure page"""
	marker = '\t' if '\t' in lines[0] else ','
	ncols = len(lines[0].split(marker))
	table_header = ["<th>Column %i <label class='checkbox'>Use<input type='checkbox' name='value' value='%i' %s></label></th>\n" % (i, i, 'checked' if str(i) in job.value else '') for i in range(1, ncols)]

	table_header = "".join(table_header)
	table_body = "".join(["<tr>\n %s</tr>\n" % "".join(["<td>%s</td>\n" % line.split(marker)[i] for i in range(1, ncols)]) for line in lines])

	return table_header, table_body, linecount, ncols

def prepare_data(job):
	"""Add auto-increment key to data, IN MEMORY and save a copy of the original data file for use in results.
	"""
	c = boto.connect_s3()
	b = c.create_bucket("dedool-user-files")	
	l = b.list(job.get_input_file().name)
	
	new_b = c.create_bucket("cleancloud")
	new_k = boto.s3.key.Key(new_b)
	new_k.key = job.get_input_file().name
	
	new_data = []

	for k in l: #l is an iterator with 1 item
		#download a copy of the input data for in-memory modification
		data = k.get_contents_as_string()
		
		#add auto-increment key and remove irrelevant columns
		for i, line in enumerate(data.split("\n")):
			if line == "\n":
				continue
			marker = '\t' if '\t' in line else ','
			if int(job.key) == 0:
				new_line = " ".join([s for j, s in enumerate(line.split(marker)) if j + 1 in map(int, job.value.split(","))])
				new_data.append(", ".join([str(i + 1), new_line]))
			else:
				new_line = " ".join([s for j, s in enumerate(line.split(marker)) if j in map(int, job.value)])
				new_data.append(", ".join([str(job.key), new_line]))

		#save modified data to S3 bucket for input data
		new_k.set_contents_from_string("\n".join(new_data))
	c.close()
	
def run_job(job):
	"""Run emr or single machine job"""
	if job.job_type == "e":
		steps = create_job_steps(job)
		jobflowid = create_job_flow(steps, job)
	else:
		run_single_machine(job)
		jobflowid = 'single'
	
	return jobflowid
		
def create_job_steps(job):
	"""Prepare job steps for EMR job"""
	steps = []
	hdfs_path = "hdfs:///%i/" % job.id	#intermediary output/input path for simplejoin
	jarpath = "s3n://simplejoin/hadoop/simplejoin.jar"
	
	if job.algorithm == 'NL':
		prepare_input = JarStep(name="Prepare Input-%i" % job.id, 
						action_on_failure="CANCEL_AND_WAIT",
						jar=jarpath, 
						main_class="com.nsrdev.PrepareInput", 
						step_args=[job.get_s3_input_path(), 
							hdfs_path, 
							job.key, 
							job.value])
		simplejoin = JarStep(name="SimpleJoin-%i" % job.id, 
						action_on_failure="CANCEL_AND_WAIT",
						jar=jarpath, 
						main_class="com.nsrdev.SimpleJoin", 
						step_args=[hdfs_path, 
							job.get_s3_output_path(), 
							job.similarity, 
							job.threshold])
		steps.append(prepare_input)
		steps.append(simplejoin)
	elif job.algorithm == 'MH':
		lsh_minhash = JarStep(name="MinHashMR-%i" % job.id, 
						action_on_failure="CANCEL_AND_WAIT",
						jar=jarpath, 
						main_class="com.nsrdev.MinHashMR", 
						step_args=[job.get_s3_input_path(), 
							job.get_s3_output_path(), 
							job.hashes, 
							job.similarity, 
							job.threshold])
		steps.append(lsh_minhash)

	return steps
	
def create_job_flow(steps, job):
	"""Start EMR job"""
	conn = boto.connect_emr()
	
	job_flows = conn.describe_jobflows(['WAITING'])
	for jf in job_flows:
		if int(jf.instancecount) >= int(job.nodes):
			conn.add_jobflow_steps(jf.jobflowid, steps)
			jobid = jf.jobflowid
			break
	else:
		jobid = conn.run_jobflow("nsr web jobflow", log_uri="s3n://nsr-logs", master_instance_type=str(job.node_size), slave_instance_type=str(job.node_size), num_instances=job.nodes, action_on_failure="CONTINUE", steps=steps, keep_alive=True)
		
	conn.close()
	return jobid

def run_single_machine(job):
	"""Start single machine job."""
	cmd = ['/home/ec2-user/sshexec.sh', job.get_input_file().name, job.get_output_file_name(), job.similarity, str(job.threshold), str(job.id)]
	print cmd
	p = subprocess.Popen(cmd)
	# p.wait()
	# print p.communicate()
		
def get_tiers(job):
	"""Return the tier description strings."""
	names = ['1-nl', '4-nl', '4-mh']
	running_times = [estimate_running_time(name, job.rows) for name in names]
	costs = [PRICES[name.split('-')[0]] * t.seconds for t, name in zip(running_times, names)]
	running_times = [str(t).split(".")[0] for t in running_times]
	
	ALGS = {'nl':'Nested loop algorithm - slow but most accurate', 'mh':'MinHash algorithm - fast, but may miss some fuzzy matches'}
	ROWS = 'Unlimited rows'
	MACHINES = {'1':'One machine', '4':'4 parallel machines', '8':'8 parallel machines', '8xl':'8 high-capacity parallel machines'}
	
	free_desc = [('Clean up to 1000 rows', 'One machine', ALGS['nl'])]
	descriptions = free_desc + [(ROWS, MACHINES[name.split('-')[0]], ALGS[name.split('-')[-1]]) for name in names[1:]]
	
	return zip(names, costs, running_times, descriptions)

def fill_job_from_service(job, service):
	"""Fill in the job details from the selected service level."""
	if "1" in service:
		job.job_type = "s"
		job.service = "free"
		job.cost = PRICES['1']
	if "nl" in service:
		job.algorithm = "NL"
	if "8" in service:
		job.nodes = 8
		job.cost = job.rows * PRICES['8']
	elif 'xl' in service:
		job.node_size = 'm1.large'
		job.cost = job.rows * PRICES['8xl']
	else:
		job.cost = job.rows * PRICES['4']
	job.save()
	
def estimate_running_time(job_type, rows):
	"""Estimate the running time of a job based on the number of rows in the input, the number of machines, and the algorithm used."""
	curve = lambda x, a, b, c: a*x**2 + b*x + c
	if "nl" in job_type:
		a, b, c = [  5.05025473e-05,   1.46056654e-02,   7.35174938e+01]
		if "4" in job_type:
			pass
		elif "8" in job_type:
			a, b, c = a/2., b/2., c/2.
		elif "1" in job_type:
			a, b, c = [1.77358211e-04, 5.06898263e-02, -2.29059299e+01]		
	elif "mh" in job_type:
		a, b, c = [  1.98641850e-06,  -4.04040423e-03,   6.10269608e+01 + 120]
		if "4" in job_type:
			pass
		if "8" in job_type:
			a, b, c = a/2., b/2., c/2.
	return datetime.timedelta(seconds=curve(rows, a, b, c))
		
def cancel_job(job):
	"""Cancel job job by terminating the EMR job flow or killing the single machine process."""
	if job.job_type == 'e':
		c = boto.connect_emr()
		c.terminate_jobflow(job.jobflowid)
	else:
		filename = job.get_input_file().name.split('/')[-1]		
		kill_cmd = "pkill -f %s" % filename

		client = paramiko.SSHClient()
		client.load_host_keys('/var/www/known_hosts')
		client.connect('10.203.87.100', 22, 'ec2-user', key_filename='/var/www/nsr-dev.pem')
		stdin, stdout, stderr = client.exec_command(kill_cmd)
		# for line in stdout:
		# 	print line
		# for line in stderr:
		# 	print line
		client.exec_command("echo CANCELLED > ~/status-output/status-s-%s.log" % filename)		
		
def check_job_submitted(job):
	"""Check if job job has already been submitted."""
	error = None
	if job.status == "completed" or job.status == "running" or job.status == "results":
		error = "Requested job has already been submitted. You can check its status <a href='%s'>here</a>." % reverse('dedool_functions.views.status', args=(job.id,))
		
	return error
	
def save_edits(job, request):
	"""Save user result edits to database."""
	for k, v in request.POST.items():
		if not (re.match("\d+-\d+", k) or re.match("\d+", k)):
			continue
		try:
			result = EditedResult.objects.get(job=job, local_id=k)
			result.value = request.POST['%s' % str(result.local_id)]
			result.save()
		except EditedResult.DoesNotExist:
			result = EditedResult(job=job, local_id=k, value=v)
			result.save()
			
def mark_row_for_deletion(job, row_id, checked):
	"""Mark row for deletion in the database."""
	try:
		result = EditedResult.objects.get(job=job, local_id=row_id)
		result.value = checked
		result.save()
	except EditedResult.DoesNotExist:
		result = EditedResult(job=job, local_id=row_id, value=checked)
		result.save()

def mark_secondary_rows_for_deletion(job):
	results = match_results(job).items()
	for id1, result_set in results:
		for id2 in result_set:
			mark_row_for_deletion(job, id2, True)


def get_redirect_from_job_status(job):
	if job.status == "unsubmitted":
		return redirect('dedool_functions.views.select', job.id)
	elif job.status == "uploaded":
		return redirect('dedool_functions.views.review', job.id)	
	elif job.status == "reviewed":
		return redirect('dedool_functions.views.configure', job.id)
	elif job.status == "running" or job.status == "results":
		return redirect('dedool_functions.views.status', job.id)
	else:
		return redirect('dedool_functions.views.status', job.id)

def user_file_is_unique(user, filename):
	for uf in UserFile.objects.filter(user=user):
		if filename in uf.input_file.name:
			return False
	return True
	
def remove_user_file(user_file):
	try:
		c = boto.connect_s3()
		b = c.create_bucket(USER_FILE_BUCKET)
		k = boto.s3.key.Key(b)
		k.key = user_file.input_file.name
		k.delete()
	except:
		return False
	finally:
		return user_file.input_file.name
		
def get_sample_file_library():	
	sample_files = UserFile.objects.filter(type="S")
	sample_files = [(f, str("".join(f.input_file.name.split("/")[-1]))) for f in sample_files if len(f.input_file.name) > 0]	
	return sample_files
	
def create_sample_file_library():
	import os, pickle
	from django.core.files import File as DjangoFile
	
	prefix = "/var/www/sample/"
	sample_files = ["celebrity.txt", "birdNybirdExtracted.txt", "dbgen-1k_input.txt", "restaurant.txt"]
	
	for fn in sample_files:
		with open(prefix + fn) as f:		
			lines = f.readlines()
			f.seek(0)
			rows = len(lines)
			columns = len(lines[0].split("\t" if "\t" in lines[0] else ","))
			statinfo = os.stat(prefix + fn)
			size = statinfo.st_size
						
			uf = UserFile(user=User.objects.get(id=1), input_file=DjangoFile(f), size=size, rows=rows, columns=columns, type="S")
			uf.save()

def strip_filename(name):
	if "_" in name:
		name = str("".join(name.split("/")[-1].split("_")[1:]))	
	else:
		name = str("".join(name.split("/")[-1]))
	return name	
	
def get_user_file_library(user, view):
	files = UserFile.objects.filter(user=user)	
	if view == "files":
		files = [(f, strip_filename(f.input_file.name)) for f in files if len(f.input_file.name) > 0 and f.type != "S"]
	elif view == "select":
		files = [(f, strip_filename(f.input_file.name)) for f in files if len(f.input_file.name) > 0 and f.type != "S" and f.type != "O"]		
	return files
	
def get_active_jobs(user):
	return Job.objects.filter((Q(status="uploaded") | Q(status="reviewed") | Q(status="unsubmitted") | Q(status="running")), user=user)	