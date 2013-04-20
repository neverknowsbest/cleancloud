from django.db import models
from django.core.validators import RegexValidator
from django.db.models.signals import post_save
from django.contrib.auth.models import User

from dedool_jobs.views import Job


class UserProfile(models.Model):
    #A user profile can have many jobs
    jobs = models.ManyToManyField(Job)
    #1 profile per user, 1 user per profile
    user = models.OneToOneField(User)
    first_name = models.CharField(max_length=100, blank=True, verbose_name=u'First Name')
    last_name = models.CharField(max_length=100, blank=True, verbose_name=u'Last Name')
    street_address_1 = models.CharField(max_length=100, blank=True)
    street_address_2 = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zipcode = models.IntegerField(max_length=5, default=0, blank=True)
    company = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=10, verbose_name=u'Phone Number',
                             help_text='Numbers only, no spaces or dashes.',
                             validators=[RegexValidator(regex='\d{10}',
                                                        message='Must consist of exactly 10 digits.')],
                             blank=True)

    def __unicode__(self):
        return "%s's profile %s" % (self.user, self.first_name)


#Automatically create user profile and connect it to the User when a new User is created
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        profile, created = UserProfile.objects.get_or_create(user=instance)
post_save.connect(create_user_profile, sender=User)
