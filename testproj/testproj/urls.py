from __future__ import absolute_import, unicode_literals

import json

from django.conf.urls import url, include
from django.contrib import admin
from django.contrib.auth.models import User
from django.http import HttpResponse

from rest_framework.authtoken.views import obtain_auth_token
from rest_framework import serializers

from testapp.models import SubscriberLog


def user_detail(request):
    raise Exception('foo')


def log_event(request, event):
    ref = request.GET.get('ref')
    SubscriberLog.objects.create(
        event=event,
        ref=ref,
        data=request.body,
        subscription=request.META.get('HTTP_HOOK_SUBSCRIPTION'),
        hmac=request.META.get('HTTP_HOOK_HMAC'),
    )
    return HttpResponse(json.dumps({'event': event, 'ref': ref}))


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        exclude = ('user_permissions',)

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^api-auth/', include(
        'rest_framework.urls', namespace='rest_framework')),
    url(r'^api-token-auth/', obtain_auth_token),
    url(r'^hooks/', include(
        'thorn.django.rest_framework.urls', namespace='webhook')),
    url(r'^user/', user_detail, name='user-detail'),
    url(r'^article/', include(
        'testapp.urls', namespace='article',
    )),
    url(r'^r/(?P<event>.+?)/', log_event, name='event-log'),
]
