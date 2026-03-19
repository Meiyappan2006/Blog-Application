from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, Http404, JsonResponse
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User, Group
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.sites.shortcuts import get_current_site
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes 
from django.conf import settings

import logging
import urllib.error
import urllib.request
import json
import time
import os

from .models import Category, Post, AboutUs, Profile, Comment, Message, ContactMessage
from .forms import (
    ContactForm, ForgotPasswordForm, PostForm, ResetPasswordForm,
    RegisterForm, LoginForm, CommentForm, UserUpdateForm, ProfileUpdateForm
)
# Create your views here.

# static demo data
# posts = [
#         {'id':1, 'title': 'Post 1', 'content': 'Content of Post 1'},
#         {'id':2, 'title': 'Post 2', 'content': 'Content of Post 2'},
#         {'id':3, 'title': 'Post 3', 'content': 'Content of Post 3'},
#         {'id':4, 'title': 'Post 4', 'content': 'Content of Post 4'},   
#     ]
def landing(request):
    return render(request, 'blog/landing.html')

def profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    is_following = False
    has_requested = False
    is_private = profile_user.profile.is_private
    can_view_posts = True  # default: public profile

    if request.user.is_authenticated:
        is_following = request.user in profile_user.profile.followers.all()
        has_requested = request.user in profile_user.profile.follow_requests.all()
        if is_private and not is_following and request.user != profile_user:
            can_view_posts = False

    # Only show posts if allowed
    posts = Post.objects.filter(user=profile_user, is_published=True).order_by('-created_at') if can_view_posts else Post.objects.none()

    context = {
        'profile_user': profile_user,
        'posts': posts,
        'is_following': is_following,
        'has_requested': has_requested,
        'is_private': is_private,
        'can_view_posts': can_view_posts,
    }
    return render(request, 'blog/profile.html', context)

@login_required
def toggle_follow(request, username):
    target_user = get_object_or_404(User, username=username)
    if request.user == target_user:
        return redirect('blog:profile', username=username)

    profile_obj = target_user.profile

    if request.user in profile_obj.followers.all():
        # Unfollow
        profile_obj.followers.remove(request.user)
    elif profile_obj.is_private:
        # Private account — toggle the follow request
        if request.user in profile_obj.follow_requests.all():
            profile_obj.follow_requests.remove(request.user)  # Cancel request
        else:
            profile_obj.follow_requests.add(request.user)     # Send request
    else:
        # Public account — follow directly
        profile_obj.followers.add(request.user)

    return redirect('blog:profile', username=username)

@login_required
def accept_follow(request, username):
    """Profile owner accepts a follow request."""
    requester = get_object_or_404(User, username=username)
    profile_obj = request.user.profile
    if requester in profile_obj.follow_requests.all():
        profile_obj.follow_requests.remove(requester)
        profile_obj.followers.add(requester)
    return redirect('blog:edit_profile')

@login_required
def decline_follow(request, username):
    """Profile owner declines a follow request."""
    requester = get_object_or_404(User, username=username)
    profile_obj = request.user.profile
    profile_obj.follow_requests.remove(requester)
    return redirect('blog:edit_profile')

@login_required
def inbox(request):
    """Show all unique conversations involving the current user."""
    from .models import Message
    from django.db.models import Q, Max
    # Get all users who have exchanged messages with current user
    sent_to = Message.objects.filter(sender=request.user).values_list('receiver', flat=True).distinct()
    received_from = Message.objects.filter(receiver=request.user).values_list('sender', flat=True).distinct()
    convo_user_ids = set(list(sent_to) + list(received_from))
    conversations = []
    for uid in convo_user_ids:
        other_user = User.objects.get(pk=uid)
        last_msg = Message.objects.filter(
            Q(sender=request.user, receiver=other_user) | Q(sender=other_user, receiver=request.user)
        ).order_by('-created_at').first()
        unread_count = Message.objects.filter(sender=other_user, receiver=request.user, is_read=False).count()
        conversations.append({'user': other_user, 'last_msg': last_msg, 'unread': unread_count})
    # Sort by latest message
    conversations.sort(key=lambda x: x['last_msg'].created_at if x['last_msg'] else 0, reverse=True)
    unread_total = Message.objects.filter(receiver=request.user, is_read=False).count()
    return render(request, 'blog/messages_inbox.html', {'conversations': conversations, 'unread_total': unread_total})

@login_required
def conversation(request, username):
    """Show & send messages between current user and another user."""
    from .models import Message
    from django.db.models import Q
    other_user = get_object_or_404(User, username=username)
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            Message.objects.create(sender=request.user, receiver=other_user, content=content)
        return redirect('blog:conversation', username=username)
    # Mark received messages as read
    Message.objects.filter(sender=other_user, receiver=request.user, is_read=False).update(is_read=True)
    messages_qs = Message.objects.filter(
        Q(sender=request.user, receiver=other_user) | Q(sender=other_user, receiver=request.user)
    ).order_by('created_at')
    return render(request, 'blog/messages_chat.html', {'other_user': other_user, 'messages': messages_qs})


def index(request):
    blog_title = "Latest Posts"

    # getting data from post model
    all_posts = Post.objects.filter(is_published=True)

    # paginate
    paginator = Paginator(all_posts, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request,'blog/index.html', {'blog_title': blog_title, 'page_obj': page_obj})

def detail(request, slug):
    post = get_object_or_404(Post, slug=slug)
    related_posts = Post.objects.filter(category=post.category).exclude(pk=post.id)[:3]
    
    is_liked = False
    is_saved = False
    if request.user.is_authenticated:
        is_liked = post.likes.filter(id=request.user.id).exists()
        is_saved = post.saves.filter(id=request.user.id).exists()
        
    comment_form = CommentForm()
    
    return render(request, 'blog/detail.html', {
        'post': post, 
        'related_posts': related_posts,
        'is_liked': is_liked,
        'is_saved': is_saved,
        'comment_form': comment_form
    })

def old_url_redirect(request):
    return redirect(reverse('blog:new_page_url'))

def new_url_view(request):
    return HttpResponse("This is the new URL")

def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            # Save to database
            contact_msg = ContactMessage.objects.create(
                name=form.cleaned_data['name'],
                email=form.cleaned_data['email'],
                message=form.cleaned_data['message']
            )

            # Send email
            subject = f"New Contact Form Submission from {contact_msg.name}"
            email_message = f"Name: {contact_msg.name}\nEmail: {contact_msg.email}\n\nMessage:\n{contact_msg.message}"
            recipient_list = [getattr(settings, 'CONTACT_EMAIL', 'menu062006@gmail.com')]
            
            try:
                send_mail(
                    subject,
                    email_message,
                    settings.DEFAULT_FROM_EMAIL,
                    recipient_list,
                    fail_silently=False,
                )
            except Exception as e:
                # Log the error but don't break the user experience
                logger = logging.getLogger("TESTING")
                logger.error(f"Error sending contact email: {e}")

            success_message = 'Your message has been sent successfully!'
            return render(request, 'blog/contact.html', {'form': ContactForm(), 'success_message': success_message})
        else:
            logger = logging.getLogger("TESTING")
            logger.debug('Form validation failure')
            return render(request,'blog/contact.html', {'form':form})
    return render(request,'blog/contact.html', {'form': ContactForm()})

def about(request):
    about_content = """
    We started SuperBlog with a radical yet simple vision: writing shouldn't be complicated. 
    <br><br>
    In a world dominated by noisy algorithmic feeds, clickbait, and endless distractions, we wanted to build a sanctuary for deep thoughts and deliberate reading.
    <br><br>
    Whether you are an aspiring writer sharing your journey, a seasoned professional dropping industry insights, or just someone who loves the quiet intimacy of an exquisitely formatted article, you belong here.
    <br><br>
    Join tens of thousands of authors who trust SuperBlog as their publishing home. Your words matter—let them shine.
    """
    return render(request,'blog/about.html',{'about_content':about_content})

def help_view(request):
    return render(request, 'blog/help.html')

def terms_view(request):
    return render(request, 'blog/terms.html')

def privacy_view(request):
    return render(request, 'blog/privacy.html')

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])  # Hash the password
            user.save()
            #add user to authors group
            authors_group,created = Group.objects.get_or_create(name="Authors")
            user.groups.add(authors_group)
            messages.success(request, 'Registration successful! You can now log in.')
            return redirect('blog:login')  # Redirect to the login page or another page
    else:
        form = RegisterForm()
    return render(request, 'blog/register.html', {'form': form})

def login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(username=username, password=password)
            if user is not None:
                auth_login(request,user)
                return redirect('blog:dashboard')
    else:
        form = LoginForm()
    
    return render(request, 'blog/login.html', {'form': form})

def dashboard(request):
    blog_title = "My Posts"
    #getting user posts
    all_posts = Post.objects.filter(user=request.user)

    # paginate
    paginator = Paginator(all_posts, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request,'blog/dashboard.html', {'blog_title': blog_title, 'page_obj': page_obj})

def logout(request):
    auth_logout(request) 
    return redirect('blog:index')  # Redirect to the Home page 

def forgot_password(request):
    form = ForgotPasswordForm()
    if request.method == 'POST':
        #form
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.get(email=email)
            #send email to reset password
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            current_site = get_current_site(request)
            domain = current_site.domain
            subject = "Reset Password Requested"
            message = render_to_string('blog/reset_password_email.html', {
                'domain': domain,
                'uid': uid,
                'token': token
            })

            send_mail(subject, message, 'noreply@menucode.com', [email])
            messages.success(request, 'Email has been sent')


    return render(request,'blog/forgot_password.html', {'form': form})


def reset_password(request, uidb64, token):
    form = ResetPasswordForm()
    if request.method == 'POST':
        #form
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['new_password']
            try:
                uid = urlsafe_base64_decode(uidb64)
                user = User.objects.get(pk=uid)
            except(TypeError, ValueError, OverflowError, User.DoesNotExist):
                user = None

            if user is not None and default_token_generator.check_token(user, token):
                user.set_password(new_password)
                user.save()
                messages.success(request, 'Your password has been reset successfully!')
                return redirect('blog:login')
            else :
                messages.error(request,'The password reset link is invalid')

    return render(request,'blog/reset_password.html', {'form': form})

@login_required
def new_post(request):
    categories = Category.objects.all()
    form = PostForm()
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        ai_raw_prompt = request.POST.get('ai_raw_prompt', '').strip()
        if form.is_valid():
            post = form.save(commit=False)
            post.user = request.user
            post.is_published = True

            # If user used AI image generator, generate via HuggingFace on the server and save.
            if ai_raw_prompt and not request.FILES.get('img_url'):
                img_bytes = _generate_image_bytes(ai_raw_prompt)
                if img_bytes:
                    from django.core.files.base import ContentFile
                    safe_name = "".join(c if c.isalnum() else "_" for c in ai_raw_prompt[:30])
                    post.img_url.save(f"ai_{safe_name}.jpg", ContentFile(img_bytes), save=False)

            post.save()
            messages.success(request, 'Story published successfully! ✓')
            return redirect('blog:dashboard')
    return render(request, 'blog/new_post.html', {'categories': categories, 'form': form})

@login_required
def edit_post(request, post_id):
    categories = Category.objects.all()
    post = get_object_or_404(Post, id=post_id)
    if post.user != request.user and not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("You do not have permission to edit this post.")
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, instance=post)
        ai_raw_prompt = request.POST.get('ai_raw_prompt', '').strip()
        if form.is_valid():
            post_obj = form.save(commit=False)
            post_obj.is_published = True

            if ai_raw_prompt and not request.FILES.get('img_url'):
                img_bytes = _generate_image_bytes(ai_raw_prompt)
                if img_bytes:
                    from django.core.files.base import ContentFile
                    safe_name = "".join(c if c.isalnum() else "_" for c in ai_raw_prompt[:30])
                    post_obj.img_url.save(f"ai_{safe_name}.jpg", ContentFile(img_bytes), save=False)

            post_obj.save()
            messages.success(request, 'Story updated and published! ✓')
            return redirect('blog:dashboard')
    else:
        form = PostForm(instance=post)
    return render(request, 'blog/edit_post.html', {'categories': categories, 'post': post, 'form': form})

@login_required
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if post.user != request.user and not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("You do not have permission to delete this post.")
    post.delete()
    messages.success(request, 'Post Deleted Succesfully!')
    return redirect('blog:dashboard')

@login_required
def publish_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if post.user != request.user and not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("You do not have permission to publish this story.")
    post.is_published = True
    post.save()
    messages.success(request, 'Story Published Successfully!')
    return redirect('blog:dashboard')

@login_required
def edit_profile(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('blog:edit_profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    my_posts = Post.objects.filter(user=request.user)
    saved_posts = request.user.saved_posts.all()

    context = {
        'u_form': u_form,
        'p_form': p_form,
        'my_posts': my_posts,
        'saved_posts': saved_posts
    }
    return render(request, 'blog/edit_profile.html', context)

@login_required
def toggle_like(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if post.likes.filter(id=request.user.id).exists():
        post.likes.remove(request.user)
    else:
        post.likes.add(request.user)
    return redirect('blog:detail', slug=post.slug)

@login_required
def toggle_save(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if post.saves.filter(id=request.user.id).exists():
        post.saves.remove(request.user)
    else:
        post.saves.add(request.user)
    return redirect('blog:detail', slug=post.slug)

@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.user = request.user
            comment.save()
            messages.success(request, 'Comment added successfully!')
    return redirect('blog:detail', slug=post.slug)

def admin_gateway(request):
    show_register = request.GET.get('mode') == 'register'
    secret_code = ""
    
    if request.method == 'POST':
        action = request.POST.get('action')
        code = request.POST.get('secret_code')
        
        # Access is granted if code is correct OR they already have the secret session flag
        has_access = (code == '060706') or (request.session.get('is_secret_admin', False))
        
        if has_access:
            secret_code = '060706' # Ensure we have it for the next form if needed
            if action == 'register_admin':
                username = request.POST.get('username')
                email = request.POST.get('email')
                password = request.POST.get('password')
                
                if User.objects.filter(username=username).exists():
                    messages.error(request, 'Entity ID already exists in system.')
                    show_register = True
                else:
                    user = User.objects.create_superuser(username=username, email=email, password=password)
                    messages.success(request, f'ROOT ACCESS ESTABLISHED: {username} IS NOW SYSTEM_ROOT.')
                    request.session['is_secret_admin'] = True
                    # Auto login
                    from django.contrib.auth import authenticate, login as auth_login
                    user = authenticate(username=username, password=password)
                    if user:
                        auth_login(request, user)
                    return redirect('blog:super_dashboard')
            else:
                # Just validating code
                request.session['is_secret_admin'] = True
                messages.success(request, 'Access Granted. Welcome, Administrator.')
                return redirect('blog:super_dashboard')
        else:
            messages.error(request, 'Access Denied: Invalid Security Code.')
    
    # Check if user reached here by asking to register (e.g. they know the code but want to see the form)
    # Or if we just failed a registration attempt (show_register will be true)
    
    return render(request, 'blog/admin_gateway.html', {
        'show_register': show_register,
        'secret_code': secret_code,
    })

def super_dashboard(request):
    if not request.session.get('is_secret_admin', False):
        return redirect('blog:admin_gateway')
    
    users = User.objects.all().order_by('-date_joined')
    posts = Post.objects.all().order_by('-created_at')
    
    total_users = users.count()
    total_posts = posts.count()
    total_comments = Comment.objects.count()
    # Saves is a M2M. The simplest counter is iterating or aggregating if 'through' errors out. We'll use sum for safety.
    total_saves = sum(p.saves.count() for p in posts)

    context = {
        'users': users,
        'posts': posts,
        'total_users': total_users,
        'total_posts': total_posts,
        'total_comments': total_comments,
        'total_saves': total_saves
    }
    return render(request, 'blog/super_dashboard.html', context)

def admin_delete_post(request, post_id):
    if not request.session.get('is_secret_admin', False):
        return redirect('blog:admin_gateway')
    post = get_object_or_404(Post, id=post_id)
    post.delete()
    messages.success(request, 'Post permanently deleted.')
    return redirect('blog:super_dashboard')

def admin_delete_user(request, user_id):
    if not request.session.get('is_secret_admin', False):
        return redirect('blog:admin_gateway')
    if user_id == request.user.id:
        messages.error(request, 'You cannot delete yourself!')
        return redirect('blog:super_dashboard')
    user = get_object_or_404(User, id=user_id)
    user.delete()
    messages.success(request, 'User permanently deleted.')
    return redirect('blog:super_dashboard')

import json
from django.http import JsonResponse

@login_required
def generate_story(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            prompt = data.get('prompt', '')
            if not prompt:
                return JsonResponse({"error": "Prompt is required"}, status=400)
            
            from django.conf import settings
            api_key = getattr(settings, 'GEMINI_API_KEY', '')
            if not api_key:
                return JsonResponse({"error": "Gemini Engine offline. API Key missing."}, status=500)
                
            import urllib.request
            
            # We'll try a sequence of models to find one with available quota
            # Standard model names for Google AI Studio / Generative Language API
            models = ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-2.0-flash-exp"]
            last_error = "Unknown Error"
            
            for model_name in models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                payload = {
                    "contents": [{
                        "parts": [{"text": f"You are a top-tier creative writer. Write a highly engaging blog post in Markdown format based on this topic: {prompt}. Do not include a title header. Output ONLY the body content. Format with headers and lists where appropriate."}]
                    }],
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048}
                }
                
                try:
                    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
                    with urllib.request.urlopen(req, timeout=30) as response:
                        res_data = json.loads(response.read().decode('utf-8'))
                        if 'candidates' in res_data and len(res_data['candidates']) > 0:
                            text = res_data['candidates'][0]['content']['parts'][0]['text']
                            return JsonResponse({"content": text})
                except urllib.error.HTTPError as e:
                    last_error = str(e)
                    # If it's an HTTP 429, we skip to the next model
                    if e.code == 429:
                        continue
                    
                    # For other HTTP errors, we try to read the body
                    err_details = last_error
                    try:
                        err_details = e.read().decode('utf-8')
                    except:
                        pass
                    return JsonResponse({"error": f"Gemini API Error ({model_name})", "details": err_details}, status=e.code)
                except Exception as e:
                    return JsonResponse({"error": f"Internal Error ({model_name})", "details": str(e)}, status=500)
            
            return JsonResponse({"error": "Gemini Quota Exhausted", "message": "All available models are currently rate-limited. Please wait 60 seconds and try again."}, status=429)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=405)

def _generate_image_bytes(prompt: str) -> bytes | None:
    """Generate an image via HuggingFace free serverless inference (FLUX.1-schnell).
    Completely free - only needs a free HuggingFace account token (no billing).
    Returns raw JPEG bytes or None on failure."""
    try:
        from django.conf import settings
        from huggingface_hub import InferenceClient
        import io
        hf_token = getattr(settings, 'HF_TOKEN', '') or ''
        if not hf_token:
            print("[AI Image] HF_TOKEN not set in settings.")
            return None
        # No provider= means HuggingFace's own FREE serverless inference is used.
        # FLUX.1-schnell is fast (3-5s), free, and generates highly relevant images.
        client = InferenceClient(api_key=hf_token)
        image = client.text_to_image(prompt, model="black-forest-labs/FLUX.1-schnell")
        # image is a PIL Image — convert to JPEG bytes
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=90)
        return buf.getvalue()
    except Exception as e:
        print(f"[AI Image] HuggingFace generation failed: {e}")
        return None


@login_required
def generate_image_proxy(request):
    """Preview proxy: generates image via HuggingFace and streams it to the browser."""
    prompt = request.GET.get('prompt', '').strip()
    if not prompt:
        return JsonResponse({"error": "Prompt is required"}, status=400)

    img_bytes = _generate_image_bytes(prompt)
    if img_bytes:
        return HttpResponse(img_bytes, content_type="image/jpeg")
    return JsonResponse({"error": "Image generation failed. Check HF_TOKEN or try a different prompt."}, status=500)


def search(request):
    """Universal search: finds posts by title/content/category, and users by username/name."""
    from django.db.models import Q
    query = request.GET.get('q', '').strip()
    
    posts = Post.objects.none()
    users = User.objects.none()
    categories = Category.objects.none()
    
    if query:
        posts = Post.objects.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(category__name__icontains=query),
            is_published=True
        ).select_related('user', 'category').distinct().order_by('-created_at')
        
        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).select_related('profile').distinct()
        
        # Topic/category matches
        categories = Category.objects.filter(name__icontains=query)

    total_results = posts.count() + users.count()
    categories_all = Category.objects.all().order_by('name')
    
    return render(request, 'blog/search.html', {
        'query': query,
        'posts': posts,
        'users': users,
        'categories': categories,
        'categories_all': categories_all,
        'total_results': total_results,
    })