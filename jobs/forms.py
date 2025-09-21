from django import forms
from .models import Job


class JobPostForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ['title', 'company', 'location', 'description', 'salary_min', 'salary_max', 'visa_sponsorship', 'latitude', 'longitude']
        widgets = {
            'description': forms.Textarea(attrs={'rows':6}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }

    def clean(self):
        cleaned = super().clean()
        # if one salary bound provided, ensure it's numeric (IntegerField handles this) and min <= max
        smin = cleaned.get('salary_min')
        smax = cleaned.get('salary_max')
        if smin is not None and smax is not None and smin > smax:
            raise forms.ValidationError('Minimum salary cannot be greater than maximum salary')
        return cleaned
