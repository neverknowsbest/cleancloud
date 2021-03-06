import boto, json, time, datetime, re, httplib, paramiko, subprocess, sys, cStringIO, multiprocessing
import numpy as np

from boto.s3.key import Key
from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse
from django.utils import timezone
from django.core.mail import send_mail
from django.db import connection

from dedool_functions.models import EditedResult
from dedool_files.models import UserFile
from cleancloud.constants import *
from cleancloud.s3ops import *

def get_accuracy(results, job):
	"""For sample datasets that include a ground truth file, calculate and return the precision & recall of the given results set."""
	base_filename = '_'.join(job.get_input_file().name.split("_")[1:]).split('.')[:-1][0]
	hits = []
	false = []

	try:
		f = open("/var/www/sample/%s.hits.txt" % base_filename)
	except IOError:
		return (-1,)

	ground = [set((int(line.split()[0]), int(line.split()[1]))) for line in f.readlines()]
	f.close()

	for line in results.split("\n"):
		if line.startswith("(") or len(line.split('\t')) > 1:
			if len(line.split('\t')) > 1:
				line = line.split('\t')[1]
			match = set([int(i) for i in line.strip("()").split(",")[:2]])
			# print >> sys.stderr, match			
			if match in ground:
				hits.append(match)
			else:
				false.append(match)

	if len(ground) > 0 and len(results) > 0:
		return (float(len(hits))/(len(hits) + len(false)), float(len(hits))/len(ground))
	else:
		return (-2,)

def get_step_status(emrid):	
	"""Get percentage complete of EMR job with jobflow id emrid.

	This screen scrapes the EMR tracker page, which is available at the job's masterpublicdnsname on port 9100. Accessing to this page is limited to whitelisted IPs, which can be set in the AWS Security Group settings page.
	"""
	emr = boto.connect_emr()
	job = emr.describe_jobflow(emrid)
	url = job.masterpublicdnsname	
	emr.close()
	
	c = httplib.HTTPConnection(url, 9100)
	c.request("GET", "/jobtracker.jsp")
	response = c.getresponse().read().split("\n")
	status_line = response[36]
	
	statuses = map(float, re.findall("<td>([0-9.]*)%<table", status_line))
	# print >> sys.stderr, statuses
	return sum(statuses)/200. * 90

def step_completed(emrid):
	"""Check if EMR job with jobflow id emrid has completed."""
	emr = boto.connect_emr()
	job = emr.describe_jobflow(emrid)
	step = job.steps[-1]
	emr.close()
	
	# print >> sys.stderr, step.state
	
	if step.state == "COMPLETED":
		return True
	else:
		return False

def get_original_data_json(job, input_id):
	"""Get original data at input_id and return it as json"""
	original = get_string_from_s3(USER_FILE_BUCKET, job.get_input_file().name).split('\n')
	marker = '\t' if '\t' in original[0] else ','
	row, column = input_id.split("-")
	
	data = original[int(row)-1].split(marker)[int(column)]
	
	return json.dumps({'original':data})
	
def check_job_status(job):
	"""Return the JSON-formatted job status. This includes the results if the job is completed."""
	if job.status == "cancelled":
		return {'status':"CANCELLED"}
	if job.job_type == "e":
		status = check_emr_job_status(job)
	else:
		status = check_single_job_status(job)

	if status['status'] == "COMPLETED" or status['status'] == "WAITING":
		job.finish_job()
		
	if job.status == "post":
		status['status'] = "WAITING"

	return status

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

def check_single_job_status(job):
	"""Check and parse single machine job status, including results if the job is finished."""
	status = get_single_status(job)
	if status >= 0 and status <= 1:
		results = ''
		state = "RUNNING"
		progress = int(status * 100.)
	elif status == -1:
		results = ''
		state = 'CANCELLED'
		progress = 0
	elif status > 1:
		state = "COMPLETED"
		progress = 100
		results = ''

	return {"results":results, "progress":progress, "status":state}

def get_results_table_rows(job, start, offset, search=None):
	"""Get [offset] rows from [start] from the results for job [job], alternately, search for word [search] and return all rows containing that word."""
	original = job.get_original_data()
	marker = '\t' if '\t' in original[0] else ','
	results = job.get_matched_rows().items()
	results.sort()
	rows = []
	ncols = len(original[0].split(marker))
	
	def get_saved_edit(row_id, cell_id, master_id):
		"""Get the saved edited result from the edited result database"""
		local_id = "%i-%i" % (row_id, cell_id) if cell_id >= 0 else int(row_id)

		try:
			edit = EditedResult.objects.get(job=job, local_id=local_id).value
			if cell_id < 0:
				if edit.lower() == "true":
					edit = True
				else:
					edit = False
		except EditedResult.DoesNotExist:
			if cell_id >= 0:
				edit = original[row_id-1].split(marker)[cell_id]
			else:
				edit = not (row_id == master_id)
		except EditedResult.MultipleObjectsReturned:
			edit = EditedResult.objects.filter(job=job, local_id=local_id)[0].value
			if cell_id < 0:
				if edit.lower() == "true":
					edit = True
				else:
					edit = False			
		# print master_id, row_id, cell_id, edit, master_id == row_id
		
		return edit
		
	def create_data_dict(master_id, row_id, n, row_class):
		"""Create the dictionary that contains the edited result data and metadata for each row in the results"""
		data = dict(((str(i+4), get_saved_edit(row_id, i, master_id)) for i in range(ncols)))
		data["0"] = "%i" % n
		data["1"] = ""
		data["2"] = "Delete"
		data["3"] = "Edit"
		data["DT_RowId"] = "%i-%i" % (master_id, master_id) if master_id == row_id else "details-%i-%i" % (master_id, row_id)
		data["DT_RowClass"] = row_class
		data["checked"] = "checked" if get_saved_edit(row_id, -1, master_id) else ""
		return data
		
	def get_search_keys():
		"""Cache search keys locally when conducting searches"""
		search_rows = set()
		for i, line in enumerate(original):
			if search.lower() in line.lower():
				search_rows.add(i+1)
				
		keys = search_rows & set(zip(*results)[0])
		rows = search_rows - keys
		
		for id1, result_set in results:
			if len(search_rows & result_set) > 0:
				keys.add(id1)
		
		return keys
		
	if search:
		keys = get_search_keys()
		result_dict = dict(results)	
		results_slice = [(k, result_dict[k]) for k in keys]
	else:
		results_slice = results#[start:start+offset]
		
	for i, (id1, result_set) in enumerate(results):
		if search and id1 not in keys:
			continue
		if not search and ((i < start) or (i >= start + offset)):
			continue
		
		data = create_data_dict(id1, id1, i, "top odd")
		rows.append(data)		
		for id2 in result_set:
			if id1 != id2:
				data = create_data_dict(id1, id2, i, "row-details expand-child even")
				rows.append(data)
	
	return rows, len(results)
		
def check_emr_job_status(job):
	"""Check EMR job status for job job."""
	emr_status, emr_details, url = get_jobflow_status(job.jobflowid)
	results = ''
	progress = 0

	if emr_status == "RUNNING":
		progress = 10 + get_step_status(job.jobflowid)
	elif emr_status == "STARTING":
		t_fraction = (timezone.now() - job.start_datetime).seconds/300.
		progress = t_fraction * 10
	elif emr_status == "COMPLETED":
		results = "completed"
	elif emr_status == "WAITING":
		time.sleep(1) #wait 1 second for everything to update
		if step_completed(job.jobflowid):
			results = "completed"
		else:
			emr_status = "RUNNING"
			progress = 10 + get_step_status(job.jobflowid)
	elif emr_status == "TERMINATED" or emr_status == "FAILED":
		job.cancel()
		if step_completed(job.jobflowid):
			results = "completed"
			
	return {"status":emr_status, "emr_details":emr_details, "progress":progress, "results":results, 'emr_tracker':url}
	
def get_jobflow_status(emr_id):
	"""Get the EMR jobflow state for EMR jobflow id emr_id."""
	conn = boto.connect_emr()

	jobflow = conn.describe_jobflow(emr_id)
	status = jobflow.state
	try:
		details = jobflow.laststatechangereason
		url = "http://%s:9100" % jobflow.masterpublicdnsname
	except AttributeError:
		details = ""
		url = ""

	return status, details, url

def save_results(job, user):
	"""Call the save results function in a separate process"""
	q = multiprocessing.Queue()
	p = multiprocessing.Process(target=save_results_mp, args=(job, user, q))
	p.start()
	print "Queue", q.get()

def save_results_mp(job, user, q):
	"""Create final results file. The rows in marked_rows will not be included in the final file. If any edited results exist in the EditedResult database, a new row will be created with the contents of the EditedResult.
	
	marked_rows - array of row IDs to be deleted
	"""
	connection.close() #needed bc Django + multiprocessing = messy
	results_csv = []
	
	original = get_string_from_s3(USER_FILE_BUCKET, job.get_input_file().name).split('\n')
	marker = '\t' if '\t' in original[0] else ','
	ncols = job.get_user_file().columns
	
	#generate data file
	for i, line in enumerate(original):
		if line == "\n": continue
		edited = []	
		try:
			marked_delete = False if EditedResult.objects.get(job=job, local_id=(i+1)).value.lower() == "false" else True
		except EditedResult.DoesNotExist:
			marked_delete = False
		except EditedResult.MultipleObjectsReturned:
			marked_delete = False if EditedResult.objects.filter(job=job, local_id=(i+1))[0].value.lower() == "false" else True
			
		if not marked_delete:
			#if row is checked, don't include in final data file
			line = line.split(marker)
			if len(line) != ncols:
				edited = ','.join(line)
			else:	
				for j in range(ncols):
					try:
						edited.append(EditedResult.objects.get(job=job, local_id='%i-%i' % (i+1, j)).value)
					except EditedResult.DoesNotExist:
						edited.append(line[j])
					except EditedResult.MultipleObjectsReturned:
						edited.append(EditedResult.objects.filter(job=job, local_id='%i-%i' % (i+1, j))[0].value)
				edited = ','.join(edited)
			results_csv.append(edited)
		if float(i)/len(original) % 10./len(original) == 0:
			q.put(float(i)/len(original))
	nrows = len(results_csv)
	results_csv = "\n".join(results_csv)
	
	latest = UserFile.objects.latest('id')
	output_file = ContentFile(results_csv)
	output_file.name = "%s.%i.%i.cleaned.csv" % 	(".".join(job.get_input_file().name.split(".")[:-1]), job.id, latest.id + 1)

	try:
		uf = UserFile.filter(jobs=job).order_by('id').reverse()[0]
		uf.input_file = output_file
		uf.save()
	except:
		uf = UserFile(input_file=output_file, user=user, size=output_file.size, rows=nrows, columns=ncols, type="O")
		uf.save()
	finally:
		uf.jobs.add(job)
		uf.save()

	job.set_status("results")
	q.put(100.)
	email_body = lambda name: \
"""
Hello,

The final results for your file cleaning job, %s are ready! You can download your results here:
http://dedool.com/files/

Thank you,
The Dedool.com team
""" % (name)	
	send_mail("Dedool.com Final Results for Job %s Ready!" % job.name, email_body(job.name), "support@nittanysystem.com", [job.user.email])	