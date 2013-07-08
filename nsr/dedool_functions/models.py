from django.db import models


class EditedResult(models.Model):
	job = models.ForeignKey('dedool_jobs.Job')
	local_id = models.CharField(max_length=31)
	value = models.TextField()
	
	def __unicode__(self):
		return '-'.join([str(self.job.id), str(self.local_id), self.value])