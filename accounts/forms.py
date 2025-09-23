from django import forms
from .models import Profile
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model


User = get_user_model()


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))

    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class': 'form-control'}),
    )
    password2 = forms.CharField(
        label="Password confirmation",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class': 'form-control'}),
        strip=False,
    )

    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # remove default help_text for password fields so requirements only appear as errors
        self.fields['password1'].help_text = None
        self.fields['password2'].help_text = None

        # apply bootstrap class to non-specified fields
        for name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'

    # recruiter flag and optional company for recruiters
    is_recruiter = forms.BooleanField(required=False, label="I am a recruiter", widget=forms.CheckboxInput())
    company = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}), label="Company (if recruiter)")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'headline', 'bio', 'skills', 'experience', 'education', 'github', 'linkedin', 'website', 'avatar',
            'company', 'desired_positions', 'desired_companies',
            'phone',
            # visibility toggles
            'headline_visible', 'bio_visible', 'skills_visible', 'experience_visible', 'education_visible',
            'links_visible', 'company_visible', 'desired_positions_visible', 'desired_companies_visible', 'phone_visible', 'email_visible',
        ]
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'experience': forms.Textarea(attrs={'rows': 4}),
            'education': forms.Textarea(attrs={'rows': 3}),
            'skills': forms.TextInput(attrs={'placeholder': 'e.g. Python, Django, SQL'}),
            'avatar': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'company': forms.TextInput(attrs={'class': 'form-control'}),
            'desired_positions': forms.Textarea(attrs={'rows': 2, 'placeholder': 'e.g. Backend Engineer, Data Analyst'}),
            'desired_companies': forms.Textarea(attrs={'rows': 2, 'placeholder': 'e.g. Acme Inc, OpenAI'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'headline_visible': forms.CheckboxInput(),
            'bio_visible': forms.CheckboxInput(),
            'skills_visible': forms.CheckboxInput(),
            'experience_visible': forms.CheckboxInput(),
            'education_visible': forms.CheckboxInput(),
            'links_visible': forms.CheckboxInput(),
            'company_visible': forms.CheckboxInput(),
            'desired_positions_visible': forms.CheckboxInput(),
            'desired_companies_visible': forms.CheckboxInput(),
            'phone_visible': forms.CheckboxInput(),
            'email_visible': forms.CheckboxInput(),
        }

    # Expose the email for editing on the profile form (pre-filled in view)
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
