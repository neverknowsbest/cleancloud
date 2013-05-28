from django.db.models.signals import post_save
from django.contrib.auth.models import User

from dedool_profile.models import create_user_profile

post_save.connect(create_user_profile, sender=User)