from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from dedool_profile.forms import UserProfileForm


@login_required
def profile(request):
    """
    Edit or add auxiliary account information such as name, address, etc. This data goes into the
    UserProfile model, not the User model, which is only for authentication.
    """
    user = request.user

    if request.method == 'POST':    # If profile form was submitted.
        form = UserProfileForm(request.POST, instance=request.user.userprofile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile details updated.')
            return redirect('profile')
        else:
            messages.error(request, 'Update failed. Please correct the errors below.')
            return render(request, 'dedool_profile/profile.html', {'form': form, 'user': user})
    else:
        form = UserProfileForm(instance=request.user.userprofile)
        return render(request, 'dedool_profile/profile.html', {'form': form, 'user': user})
