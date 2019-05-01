# -*- coding: utf-8 -*-



from django.db import models
from django.contrib.auth.models import User

# IMPORTANT to register everything #
from . import views


class Profile(models.Model):
    user = models.OneToOneField(User)
