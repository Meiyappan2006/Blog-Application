from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User

# Category
class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

# Create your models here.
class Post(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()
    img_url = models.ImageField(null=True, upload_to="posts/images")
    created_at = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(unique=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    is_published = models.BooleanField(default=False)
    likes = models.ManyToManyField(User, related_name='liked_posts', blank=True)
    saves = models.ManyToManyField(User, related_name='saved_posts', blank=True)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def formatted_img_url(self):
        if self.img_url:
            url = self.img_url if self.img_url.__str__().startswith(('http://','https://')) else self.img_url.url
            return url
        return None

    def __str__(self):
        return self.title

class AboutUs(models.Model):
    content = models.TextField()

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True)
    profile_pic = models.ImageField(null=True, blank=True, upload_to="profile_pics/")
    followers = models.ManyToManyField(User, related_name='following', blank=True)
    # Privacy settings
    is_private = models.BooleanField(default=False)
    follow_requests = models.ManyToManyField(User, related_name='pending_follow_requests', blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    @property
    def formatted_profile_pic(self):
        if self.profile_pic:
            url = self.profile_pic if self.profile_pic.__str__().startswith(('http://','https://')) else self.profile_pic.url
            return url
        return "https://ui-avatars.com/api/?name=" + str(self.user.username) + "&background=random"

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Comment by {self.user.username} on {self.post.title}'


class Message(models.Model):
    """Direct message between two users."""
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'From {self.sender.username} to {self.receiver.username}: {self.content[:40]}'

class ContactMessage(models.Model):
    """Message from the contact form."""
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.name} ({self.email})"
