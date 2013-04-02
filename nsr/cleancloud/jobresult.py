from status import *

class JobResult(object):
	"""This class handles all results for a given job, including generating the result preview, generating the final HTML, downloadable file, etc."""

	def __init__(self, job):
		self.job = job
		
	def get_public_results_link(self):
		"""Return the publicly accessible link to the file containing the final results for job job."""
		result_file = "%s.cleaned.csv" % ".".join(self.job.input_file.name.split(".")[:-1])
		public_s3_file = "http://s3.amazonaws.com/cleancloud/cleaned/" + result_file	
		return public_s3_file

	def get_final_results_table(self):
		"""Return the table containing the full, final results for job job."""
		result_file = "%s.cleaned.csv" % ".".join(self.job.input_file.name.split(".")[:-1])	
		results = get_string_from_s3("cleancloud", "cleaned/" + result_file).split('\n')
		marker = '\t' if '\t' in results[0] else ','
	
		table_header = "<tr>\n %s </tr>" % "".join(["<th>Column %i</td>\n" % (i + 1) for i in range(len(results[0].split(marker)))])
		table_body = "".join(["<tr>\n %s</tr>\n" % "".join(["<td>%s</td>\n" % column_data for column_data in line.split(marker)]) for line in results])
		table_string = "<table class='table'>%s %s</table>" % (table_header, table_body)

		return table_string

	def match_results(self, results):
		"""Match and split results in results according to job.similarity."""
		result_dict = {}
		if self.job.similarity == "SoftTFIDF":
			results = re.findall("\((\d*),(\d*),(.*),(.*),(.*)\nscore = ([.0-9]*)\)", results)
		elif self.job.similarity == "Jaccard":
			results = re.findall("\((\d*),(\d*),(.*),(.*),(.*)\n(.*)\nscore = ([.0-9]*)\)", results)
			results = [(id1, id2, val1, val2, d1 + d2, score) for (id1, id2, val1, val2, d1, d2, score) in results]
		elif self.job.similarity == "Level2JaroWinkler":
			results = re.findall("\((\d+),(\d+),(.+?),(.+?),(.+?)\ntotal: [.0-9]*/[.0-9]* = ([.0-9]*)\n\)", results)
		
		results = sorted([(int(id1), int(id2)) for (id1, id2, val1, val2, details, score) in results])
	
		for id1, id2 in results:
			result_dict.setdefault(id1, set()).add(id2)

		return result_dict

	def get_result_table_rows(self, i, id1, result_set, original):
		def close_button(rowid):
			return """
	<td>
		<label onclick="display_details('%i')"><i id="toggle%i" class="icon-plus"></i></label>
	</td>
	""" % (rowid, rowid)
		def checkbox(rowid, checked):
			return """
	<td>
		<input type="checkbox" name="delete" value="%i" id="id_items_%i" %s>
	</td>	
			""" % (rowid, rowid, ('checked' if checked else ''))
		rows = []
		rows.append(''.join(["<tr class='top'>"] + [checkbox(i, False)] + [close_button(i)] + ["<td>%i</td>" % id1] + ["""<td onclick="send_value_to_input('%i-%i', '%s')">%s</td>""" % (id1, j, data, data) for j, data in enumerate(original[id1-1].split(marker))] + ["</tr>"]))				
			
		for row_id in result_set:
			row = ''.join(["<tr id='details%i-%i' class='row-details expand-child'>" % (i, row_id)] + [checkbox(i, True)] + ["<td></td>"] + ["<td>%i</td>" % row_id] + ["""<td onclick="send_value_to_input('%i-%i', '%s')">%s</td>""" % (id1, j, data, data) for j, data in enumerate(original[row_id-1].split(marker))] + ["</tr>"])
			rows.append(row)

		return ''.join(rows)
		
	def get_results_table_body(self, results, original):
		"""Return the table of results for the preview/edit results page. This includes the input boxes for editing the results. 
	
		results - the results to format, as a raw string
		original - the original data file, as an array of strings
		job - the job
		"""
		def edit_row_template(inputs, rowid):
			return """
	<tr id="editrow%i" class="row-details expand-child bottom">
		<td colspan="3">
			<span id="editstatus%i"></span>
		</td>
		%s
	</tr>
	"""	% (rowid, rowid, inputs)

		results_string = []
		marker = '\t' if '\t' in original[0] else ','	
		results = match_results(results, self.job)	
	
		for i, (id1, result_set) in enumerate(results.iteritems()):				
			rows = self.get_result_table_rows(i, id1, result_set, original)
		
			try:
				input_boxes = ''.join(["""<td><input id='edit%i' type='text' value='%s' name='%i-%i' onblur='save_results_changes("%i", "%i")'/></td>""" % (i, EditedResult.objects.get(job=self.job, local_id='%i-%i' % (id1, j)).value, id1, j, self.job.id, i) for j, data in enumerate(original[id1-1].split(marker))])
			except EditedResult.DoesNotExist:
				#Populate each input box with the original data value that is longest
				result_rows = np.array([original[id1].split(marker)] + [original[row_id].split(marker) for row_id in result_set])
				longer_data = [result_rows[np.argmax(map(len, result_rows[:,j])), j] for j in range(result_rows.shape[1])]
				input_boxes = ''.join(["""<td><input id='edit%i' type='text' value='%s' name='%i-%i' onblur='save_results_changes("%i", "%i")'/></td>""" % (i, data, id1, j, self.job.id, i) for j, data in enumerate(longer_data)])
			edit_row = edit_row_template(input_boxes, i)

			results_string.append(rows)
			results_string.append(edit_row)
		
		results_html = "".join(results_string)	
	
		return len(results), results_html
		
	def prepare_results(self, results):
		"Prepare table of results that is sent in the AJAX response"
		original = get_string_from_s3('cleancloud-original', job.input_file.name).split('\n')
		marker = '\t' if '\t' in original[0] else ','
		ncols = len(original[0].split(marker)) + 1
	
		elapsed_time = get_single_status(self.job) / 60.
		accuracy = get_accuracy(results, self.job)
		accuracy_string = ("<p>Accuracy/Precision: %s </p>" % str(accuracy)) if accuracy[0] > 0 else ""	
		header = ''.join(["<th></th><th></th>"] + ["<th>Row ID</th>"]+ ["<th></th>" for i in range(ncols-1)])

		n_results, results_html = self.get_results_table_body(results, original, job)

		table_string = \
	"""
	<div class="span12">
		<h2>Preview Results</h2>
		<p>Total Time: %.2f minutes</p>
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
						<input class="btn btn-large btn-primary" type="submit" value="Generate Final Results">
					</div>
				</div>
			</div>	
			<table class="tablesorter table table-hover" id="result_table">
				<thead>
				%s
				</thead>
				<tbody>
				%s
				</tbody>
			</table>
	</div>
	""" % (float(elapsed_time), accuracy_string, n_results, self.job.id, header, results_html)

		return table_string		