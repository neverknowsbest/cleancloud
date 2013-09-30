from django.db import models


class EditedResult(models.Model):
	"""A saved, cleaned result.
	
	job - foreign key relation to the job the result is from
	local_id - two-part id that indicates the row and column of the result
	value - the result value
	"""
	job = models.ForeignKey('dedool_jobs.Job')
	local_id = models.CharField(max_length=31)
	value = models.TextField()
	
	def __unicode__(self):
		return '-'.join([str(self.job.id), str(self.local_id), self.value])