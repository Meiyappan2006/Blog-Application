from django.contrib.auth.models import Group, Permission

def create_groups_permissions(sender, **kwargs):
    try:
        # create groups
        readers_group,created = Group.objects.get_or_create(name="Readers")
        authors_group,created = Group.objects.get_or_create(name="Authors")
        editors_group,created = Group.objects.get_or_create(name="Editors")

        #create permissions
        readers_permissions = [
            Permission.objects.get(codename="view_post")
        ]

        authors_permissions = [
            Permission.objects.get(codename="view_post"),
            Permission.objects.get(codename="add_post"),
            Permission.objects.get(codename="change_post"),
            Permission.objects.get(codename="delete_post"),
        ]
        can_publish,created = Permission.objects.get_or_create(codename="can_publish", content_type_id = 7, name="Can Publish Post")
        editors_permissions = [
            Permission.objects.get(codename="view_post"),
            can_publish,
            Permission.objects.get(codename="add_post"),
            Permission.objects.get(codename="change_post"),
            Permission.objects.get(codename="delete_post"),
        ]

        #assigning the permissions to groups
        readers_group.permissions.set(readers_permissions)
        authors_group.permissions.set(authors_permissions)
        editors_group.permissions.set(editors_permissions)
        print("Groups and Permissions created successfully")
    except Exception as e:
        print(f"An error occured {e}")


from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        Profile.objects.create(user=instance)