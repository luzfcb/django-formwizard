from django import forms
from django.forms.formsets import formset_factory
from django.contrib.auth.models import User


class Page1(forms.Form):
    name = forms.CharField(max_length=100)
    user = forms.ModelChoiceField(queryset=User.objects.all())
    thirsty = forms.NullBooleanField()


class Comment(forms.Form):
    name = forms.CharField(max_length=100)
    message = forms.CharField(max_length=200)

Page1Comments = formset_factory(Comment, extra=2)

class Page2(forms.Form):
    address1 = forms.CharField(max_length=100)
    address2 = forms.CharField(max_length=100)
    file1 = forms.FileField()


class Page3(forms.Form):
    random_crap = forms.CharField(max_length=100)


Page4 = formset_factory(Page3, extra=2)
