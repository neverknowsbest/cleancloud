import boto, json, time, datetime, re, httplib, paramiko, subprocess, sys, cStringIO
import numpy as np

from boto.s3.key import Key
from django.core.files import File
from django.core.urlresolvers import reverse
from django.utils import timezone

from dedool_functions.models import EditedResult
from dedool_files.models import UserFile
from cleancloud.constants import *

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
		
def get_elapsed_time(job):
	"""Get elapsed time for job."""
	if job.job_type == "e":
		return get_elapsed_time_emr(job, job.jobflowid)
	else:
		return datetime.timedelta(seconds=get_single_status(job))

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
		
def get_string_from_s3(bucket, s3filename):
	"""Get string from S3 bucket bucket, with S3 filename s3filename."""
	s3 = boto.connect_s3()
	bucket = s3.create_bucket(bucket)
	file_list = bucket.list(s3filename)

	contents = []
	for k in file_list:
		contents.append(k.get_contents_as_string())
	contents = ''.join(contents)
	s3.close()
	
	return contents		

def save_string_to_s3(contents, bucket, filename, public=False):
	"""Save string in contents to S3 bucket bucket, with S3 filename filename. If public is True, the file is publicly accessible."""
	s3 = boto.connect_s3()
	bucket = s3.create_bucket(bucket)
	k = Key(bucket)
	k.key = filename
	k.set_contents_from_string(contents)
	if public:
		k.set_acl('public-read')
	s3.close()

def get_public_results_link(job):
	"""Return the publicly accessible link to the file containing the final results for job job."""
	result_file = UserFile.objects.filter(jobs=job, type="O").order_by('id').reverse()[0]
	return result_file.get_public_link()
	
def get_final_results_table(job):
	"""Return the table containing the full, final results for job job."""
	result_file = UserFile.objects.filter(jobs=job, type="O").order_by('id').reverse()[0]
	results = get_string_from_s3(USER_FILE_BUCKET, result_file.input_file.name).split('\n')
	marker = '\t' if '\t' in results[0] else ','
	
	table_header = "<tr>\n %s </tr>" % "".join(["<th>Column %i</td>\n" % (i + 1) for i in range(len(results[0].split(marker)))])
	table_body = "".join(["<tr>\n %s</tr>\n" % "".join(["<td>%s</td>\n" % column_data for column_data in line.split(marker)]) for line in results])
	table_string = "<table class='table'>%s %s</table>" % (table_header, table_body)

	return table_string

def match_results(job):
	"""Match and split results in results according to job.similarity."""
	results = get_raw_results_data(job)	
	results = re.findall("\((\d*),(\d*),(.*),(.*)\)", results)
	result_dict = {}
		
	results = sorted([(int(id1), int(id2)) for (id1, id2, val1, val2) in results])
	
	for id1, id2 in results:
		for k, result_set in result_dict.iteritems():
			if id1 in result_set:
				result_set.add(id2)
			elif id2 in result_set:
				result_set.add(id1)
		else:
			result_dict.setdefault(id1, set()).add(id2)

	return result_dict
		
def get_results_table_body(original, job):
	"""Return the table of results for the preview/edit results page. This includes the input boxes for editing the results. 
	
	results - the results to format, as a raw string
	original - the original data, split on '\n' into an array of strings
	job - the job
	"""
	def checkbox(rowid, delete):
		return """
<td>
	<span id="editstatus%i"></span>
	<span id="id_items_%i" class="btn-group" data-toggle="buttons-radio" onclick="toggle_remove_row_button('%i', '%i')">
		<button id="button_ok_%i" type="button" class="btn btn-small btn-success %s"><i class="icon-white icon-ok"></i></button>
		<button id="button_remove_%i" type="button" class="btn btn-small btn-danger %s"><i class="icon-white icon-remove"></i></button>
	</span>
</td>	
		""" % (rowid, rowid, job.id, rowid, rowid, '' if delete else 'active', rowid, 'active' if delete else '')
	def close_button(rowid):
		return """
<td>
	<label onclick="display_details('%i')" id="toggle%i"><i class="icon-plus"></i></label>
</td>
""" % (rowid, rowid)
	def edit_row_template(inputs, rowid):
		return """
<tr id="editrow%i" class="row-details expand-child bottom">
	<td colspan="2">
		<span id="editstatus%i"></span>
	</td>
	<td width='16'><img src='/static/icons/up-right-arrow.ico'></td>
	%s
</tr>
"""	% (rowid, rowid, inputs)
	def active_column(column, job):
		return "active" if str(column+1) in job.value else "inactive"

	rows_to_delete = []
	results_string = []
	marker = '\t' if '\t' in original[0] else ','	
	results = match_results(job)	
	
	#generate table rows from original data + matched pairs from cleaning output
	for i, (id1, result_set) in enumerate(sorted(results.iteritems())):
		rows = []
		#first row, always visible
		#fill row with edited result data if available, otherwise use data from original input
		row_data = []
		for j, data in enumerate(original[id1-1].split(marker)):
			try:
				er = lambda j: EditedResult.objects.get(job=job, local_id="%i-%i" % (id1, j)).value
				row_data.append("""<td class="%s" id="cell%i-%i" onclick="send_value_to_input('%i', '%i-%i', '%s')">%s</td>""" % (active_column(j, job), id1, j, job.id, id1, j, er(j), er(j)))
			except EditedResult.DoesNotExist:
				row_data.append("""<td class="%s" id="cell%i-%i" onclick="send_value_to_input('%i', '%i-%i', '%s')">%s</td>""" % (active_column(j, job), id1, j, job.id, id1, j, data, data))
		
		#get "delete row" state from database
		try:
			delete = EditedResult.objects.get(job=job.id, local_id=id1).value
		except EditedResult.DoesNotExist:
			delete = False
		finally:
			if delete:
				rows_to_delete.append(id1)
		
		rows.append(''.join(["<tr class='top'>"] + \
			[close_button(id1)] + \
			[checkbox(id1, delete)] + \
			row_data + \
			["</tr>"]))
			
		#One or more secondary rows, hidden by default
		for k, row_id in enumerate(result_set):
			try:
				delete = EditedResult.objects.get(job=job.id, local_id=row_id).value
			except EditedResult.DoesNotExist:
				#delete secondary rows by default
				delete = True 
			finally:
				if delete:
					rows_to_delete.append(row_id)

			row_data = []
			for j, data in enumerate(original[row_id-1].split(marker)):
				try:
					er = lambda j: EditedResult.objects.get(job=job, local_id="%i-%i" % (row_id, j)).value				
					row_data.append("""<td class="%s" id="cell%i-%i" onclick="send_value_to_input('%i', '%i-%i', '%s')">%s</td>""" % (active_column(j, job), row_id, j, job.id, row_id, j, er(j), er(j)))
				except EditedResult.DoesNotExist:
					row_data.append("""<td class="%s" id="cell%i-%i" onclick="send_value_to_input('%i', '%i-%i', '%s')">%s</td>""" % (active_column(j, job), row_id, j, job.id, row_id, j, data, data))
						
			row = ''.join(["<tr id='details%i-%i' class='row-details expand-child %s'>" % (id1, row_id, 'bottom' if k == len(result_set)-1 else '')] + \
				["<td></td>"] + #close button is not needed for secondary rows \
				[checkbox(row_id, delete)] + \
				row_data + \
				["</tr>"])
			rows.append(row)
		rows = ''.join(rows)

		results_string.append(rows)
		
	results_html = "".join(results_string)	
	
	return len(results), results_html, rows_to_delete

def prepare_results_page(job):
	"Prepare table of results that is sent in the AJAX response"
	original = get_original_data(job)
	ncols = get_results_columns(job)
	
	elapsed_time = get_elapsed_time(job)
	# accuracy = get_accuracy(results, job)
	# accuracy_string = ("<p>Precision/Recall: %s </p>" % str(accuracy)) if accuracy[0] > 0 else ""
	accuracy_string = ""	
	header = ''.join(["<th></th><th>Keep Row</th>"] + ["<th></th>" for i in range(ncols-1)])

	n_results, results_html, rows_to_delete = get_results_table_body(original, job)
	
	if n_results == 0:
		job.set_status("no match")
		table_string = \
"""
<div class="span12">
	<p>No records matched.</p>
</div>
"""
	else:
		table_string = \
"""
<div class="span12">
	<h2>Preview Results</h2>
	<p>Running Time: %.2f minutes</p>
	%s
	<p><strong>%i</strong> records matched. Click the '+' button to edit the matched record. Check the box next to a row to remove that row from the final results. </p>

		<div class="form-actions">
			<div class="btn-toolbar">
				<div class="btn-group">
					<a onclick="hide_all()" class="btn"><i class="icon-minus-sign" title="Collapse All"></i></a>
					<a onclick="expand_all()" class="btn"><i class="icon-plus-sign" title="Expand All"></i></a>
					<a onclick="save_results_changes('%i')" class="btn"><i class="icon-save" title="Save All Changes"></i></a>
				</div>
					
				<div class="pull-right" id="submit">
					<input class="btn btn-large btn-primary" type="submit" id="final" value="Generate Final Results">
				</div>
			</div>
		</div>
		<input id="delete" name="delete" type="hidden" value="%s"/>
		<table class="tablesorter table table-hover" id="results_table">
			<thead>
			%s
			</thead>
			<tbody>
			%s
			</tbody>
		</table>
</div>
""" % (float(elapsed_time.seconds / 60.), accuracy_string, n_results, job.id, rows_to_delete, header, results_html)

	return table_string

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
		return json.dumps({'status':"CANCELLED"})
	if job.job_type == "e":
		status = check_emr_job_status(job)
	else:
		status = check_single_job_status(job)

	if status['status'] == "COMPLETED" or status['status'] == "WAITING":
		job.finish_datetime = job.start_datetime + get_elapsed_time(job)
		job.set_status("results")
		job.save()

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
		# results = get_results(job)

	return {"results":results, "progress":progress, "status":state}

def get_results(job):
	"""Get results table for job job."""
	results_table = prepare_results_page(job)

	return results_table

def get_original_data(job):
	"""Return original data file for job job."""
	original = get_string_from_s3(USER_FILE_BUCKET, job.get_input_file().name).split('\n')

	return original

def get_raw_results_data(job):
	return get_string_from_s3(DEDOOL_OUTPUT_BUCKET, "output/" + str(job.id) + "/" + job.get_output_file_name())

def get_results_table_rows(job, start, offset):
	"""Get [offset] rows from [start] from the results for job [job]."""
	original = get_original_data(job)
	marker = '\t' if '\t' in original[0] else ','
	results = match_results(job).items()
	results.sort()
	results_rows = len(results)
	rows = []
	ncols = len(original[0].split(marker))
		
	def get_saved_edit(row_id, cell_id, master_id):
		local_id = "%i-%i" % (row_id, cell_id) if cell_id >= 0 else str(row_id)

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
		return edit
		
	def create_data_dict(master_id, row_id, row_class):
		data = dict(((str(i+3), get_saved_edit(row_id, i, master_id)) for i in range(ncols)))
		data["0"] = ""
		data["1"] = "Delete"
		data["2"] = "Edit"
		data["DT_RowId"] = "%i-%i" % (master_id, master_id) if master_id == row_id else "details-%i-%i" % (master_id, row_id)
		data["DT_RowClass"] = row_class
		data["checked"] = "checked" if get_saved_edit(row_id, -1, master_id) else ""
		return data
		
	for id1, result_set in results[start:start+offset]:
		data = create_data_dict(id1, id1, "top odd")
		rows.append(data)		
		for id2 in result_set:
			data = create_data_dict(id1, id2, "row-details expand-child even")
			rows.append(data)
	
	return rows, results_rows
		
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
	"""Create final results file. The rows in marked_rows will not be included in the final file. If any edited results exist in the EditedResult database, a new row will be created with the contents of the EditedResult.
	
	marked_rows - array of row IDs to be deleted
	"""
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
				edited = ','.join(edited)
			results_csv.append(edited)
	nrows = len(results_csv)
	results_csv = "\n".join(results_csv)
	output_file = File(cStringIO.StringIO(results_csv))
	output_file.name = "%s.%i.cleaned.csv" % (".".join(job.get_input_file().name.split(".")[:-1]), job.id)

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