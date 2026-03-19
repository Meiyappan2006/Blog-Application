from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import authenticate

from blog.models import Category, Post, Comment, Profile

class ContactForm(forms.Form):
    name = forms.CharField(label='Name', max_length=100, required=True)
    email = forms.EmailField(label='Email',  required=True)
    message = forms.CharField(label='Message',  required=True)

class RegisterForm(forms.ModelForm):
    username = forms.CharField(label='username', max_length=100, required=True)
    email = forms.CharField(label='email', max_length=100, required=True)
    password = forms.CharField(label='password', max_length=100, required=True)
    password_confirm = forms.CharField(label='password confirm', max_length=100, required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Passwords do not match.")

class LoginForm(forms.Form):
    username = forms.CharField(label='username', max_length=100, required=True)
    password = forms.CharField(label='password', max_length=100, required=True)

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        password = cleaned_data.get("password")
        if username and password:
            user = authenticate(username=username, password=password)
            if user is None:
                raise forms.ValidationError("Invalid username or password")

class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(label='Email', max_length=254, required=True)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')

        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError("No User Registered with this email.")
        
class ResetPasswordForm(forms.Form):
    new_password = forms.CharField(label='New Password', min_length=8)
    confirm_password = forms.CharField(label='Confirm Password', min_length=8)

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")

class PostForm(forms.ModelForm):
    title = forms.CharField(label='Title', max_length=200, required=True)
    content = forms.CharField(label='Content', required=True)
    category =  forms.ModelChoiceField(label='Category', required=True, queryset=Category.objects.all())
    img_url = forms.ImageField(label='Image', required=False)

    class Meta:
        model = Post
        fields = ['title', 'content', 'category', 'img_url']

    def clean(self):
        cleaned_data = super().clean()
        title = cleaned_data.get('title')
        content = cleaned_data.get('content')

        #custom validation
        if title and len(title) < 5:
            raise forms.ValidationError('Title must be at least 5 Characters long.')
        
        if content and len(content) < 10:
            raise forms.ValidationError('Content must be at least 10 Characters long.')
    
    def save(self, commit = ...):

        post =  super().save(commit)
        cleaned_data = super().clean()

        if cleaned_data.get('img_url'):
            post.img_url = cleaned_data.get('img_url')
        else:
            img_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/No_image_available.svg/600px-No_image_available.svg.png"
            post.img_url = img_url

        if commit:
            post.save()
        return post

class CommentForm(forms.ModelForm):
    content = forms.CharField(label='', widget=forms.Textarea(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl p-4 text-gray-900 font-medium focus:ring-gray-900 focus:border-gray-900 resize-y', 'rows': 3, 'placeholder': 'Write a comment...'}))

    class Meta:
        model = Comment
        fields = ['content']

class UserUpdateForm(forms.ModelForm):
    first_name = forms.CharField(label='First Name', max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl p-3 text-gray-900 font-medium'}))
    last_name = forms.CharField(label='Last Name', max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl p-3 text-gray-900 font-medium'}))

    class Meta:
        model = User
        fields = ['first_name', 'last_name']

class ProfileUpdateForm(forms.ModelForm):
    bio = forms.CharField(label='Bio', widget=forms.Textarea(attrs={'class': 'w-full bg-gray-50 border border-gray-200 rounded-xl p-4 text-gray-900 font-medium h-32 resize-none'}), required=False)
    profile_pic = forms.ImageField(label='Profile Picture', required=False, widget=forms.FileInput(attrs={'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-gray-50 file:text-gray-900 hover:file:bg-gray-100'}))
    is_private = forms.BooleanField(label='Private Account', required=False, widget=forms.CheckboxInput(attrs={'class': 'sr-only peer', 'id': 'privacy-toggle'}))

    class Meta:
        model = Profile
        fields = ['bio', 'profile_pic', 'is_private']