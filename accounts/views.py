import json as _json
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import Customer, Seller, SuperAdmin


# ── HELPERS ───────────────────────────────────────────────────
def _redirect_if_logged_in(request):
    """Already logged-in users go to their dashboard."""
    role = request.session.get('user_role')
    if role == 'customer':
        return redirect('/')
    if role == 'seller':
        return redirect('/seller/dashboard/')
    if role == 'admin':
        return redirect('/accounts/dashboard/admin/')
    return None


def _validate_password_strength(password):
    """
    Returns (is_valid, error_message).
    Min 8 chars, at least 1 letter and 1 digit.
    """
    if len(password) < 8:
        return False, 'Password must be at least 8 characters.'
    if not any(c.isalpha() for c in password):
        return False, 'Password must contain at least one letter.'
    if not any(c.isdigit() for c in password):
        return False, 'Password must contain at least one number.'
    return True, ''


def _check_login_lockout(request, email):
    """
    Returns True if this email is locked out.
    Stores attempt count + lockout time in session.
    """
    from django.conf import settings
    max_attempts    = getattr(settings, 'MAX_LOGIN_ATTEMPTS',    5)
    lockout_minutes = getattr(settings, 'LOGIN_LOCKOUT_MINUTES', 15)

    key_attempts = f'login_attempts_{email}'
    key_lockout  = f'login_lockout_{email}'

    lockout_until = request.session.get(key_lockout)
    if lockout_until:
        lockout_dt = timezone.datetime.fromisoformat(lockout_until)
        if timezone.now() < lockout_dt:
            remaining = int((lockout_dt - timezone.now()).total_seconds() // 60) + 1
            messages.error(request,
                f'Too many failed attempts. Try again in {remaining} minute(s).')
            return True
        else:
            # Lockout expired — reset
            request.session.pop(key_lockout, None)
            request.session.pop(key_attempts, None)
    return False


def _record_failed_login(request, email):
    """Increment failed login counter; lock out after max attempts."""
    from django.conf import settings
    max_attempts    = getattr(settings, 'MAX_LOGIN_ATTEMPTS',    5)
    lockout_minutes = getattr(settings, 'LOGIN_LOCKOUT_MINUTES', 15)

    key_attempts = f'login_attempts_{email}'
    key_lockout  = f'login_lockout_{email}'

    attempts = request.session.get(key_attempts, 0) + 1
    request.session[key_attempts] = attempts
    request.session.modified = True

    if attempts >= max_attempts:
        lockout_until = timezone.now() + timezone.timedelta(minutes=lockout_minutes)
        request.session[key_lockout] = lockout_until.isoformat()
        messages.error(request,
            f'Account locked for {lockout_minutes} minutes due to too many failed attempts.')


def _clear_login_attempts(request, email):
    """Clear failed attempt counter after successful login."""
    request.session.pop(f'login_attempts_{email}', None)
    request.session.pop(f'login_lockout_{email}', None)


# ── HOME ──────────────────────────────────────────────────────
def home(request):
    return redirect('/')


# ── LOGIN ─────────────────────────────────────────────────────
def login_view(request):
    redir = _redirect_if_logged_in(request)
    if redir:
        return redir

    if request.method == 'POST':
        email    = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        role     = request.POST.get('role', '')

        # Brute-force protection
        if _check_login_lockout(request, email):
            return render(request, 'accounts/login.html')

        if role == 'customer':
            try:
                user = Customer.objects.get(email=email)
                if check_password(password, user.password):
                    _clear_login_attempts(request, email)
                    request.session['user_id']   = user.id
                    request.session['user_role'] = 'customer'
                    request.session['user_name'] = user.name
                    messages.success(request, f'Welcome back, {user.name}!')
                    return redirect(request.POST.get('next', '/'))
                _record_failed_login(request, email)
                messages.error(request, 'Incorrect password.')
            except Customer.DoesNotExist:
                messages.error(request, 'No customer account with this email.')

        elif role == 'seller':
            try:
                user = Seller.objects.get(email=email)
                if check_password(password, user.password):
                    if not user.is_approved:
                        messages.warning(request, 'Your account is pending admin approval.')
                        return redirect('accounts:login')
                    _clear_login_attempts(request, email)
                    request.session['user_id']   = user.id
                    request.session['user_role'] = 'seller'
                    request.session['user_name'] = user.name
                    # Store approval status for seller_required() checks
                    request.session['seller_approved'] = True
                    messages.success(request, f'Welcome back, {user.name}!')
                    return redirect('/seller/dashboard/')
                _record_failed_login(request, email)
                messages.error(request, 'Incorrect password.')
            except Seller.DoesNotExist:
                messages.error(request, 'No seller account with this email.')

        elif role == 'admin':
            try:
                user = SuperAdmin.objects.get(email=email)
                if check_password(password, user.password):
                    _clear_login_attempts(request, email)
                    request.session['user_id']   = user.id
                    request.session['user_role'] = 'admin'
                    request.session['user_name'] = user.username
                    messages.success(request, f'Welcome, Admin {user.username}!')
                    return redirect('/accounts/dashboard/admin/')
                _record_failed_login(request, email)
                messages.error(request, 'Incorrect password.')
            except SuperAdmin.DoesNotExist:
                messages.error(request, 'No admin account with this email.')
        else:
            messages.error(request, 'Please select a role.')

    return render(request, 'accounts/login.html')


# ── REGISTER ──────────────────────────────────────────────────
def register_view(request):
    redir = _redirect_if_logged_in(request)
    if redir:
        return redir

    if request.method == 'POST':
        name     = request.POST.get('name', '').strip()
        email    = request.POST.get('email', '').strip().lower()
        phone    = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        confirm  = request.POST.get('confirm_password', '')
        role     = request.POST.get('role', '')

        if not name or not email or not password:
            messages.error(request, 'Name, email and password are required.')
            return redirect('accounts:register')
        if password != confirm:
            messages.error(request, 'Passwords do not match.')
            return redirect('accounts:register')

        # ── Strong password validation ─────────────────────────
        valid, err = _validate_password_strength(password)
        if not valid:
            messages.error(request, err)
            return redirect('accounts:register')

        if role == 'customer':
            if Customer.objects.filter(email=email).exists():
                messages.error(request, 'An account with this email already exists.')
                return redirect('accounts:register')
            Customer.objects.create(name=name, email=email, phone=phone,
                                    password=make_password(password))
            messages.success(request, 'Account created! Please login.')
            return redirect('accounts:login')

        elif role == 'seller':
            if Seller.objects.filter(email=email).exists():
                messages.error(request, 'A seller account with this email already exists.')
                return redirect('accounts:register')
            Seller.objects.create(name=name, email=email, phone=phone,
                                  password=make_password(password))
            messages.success(request, 'Seller account created! Awaiting admin approval.')
            return redirect('accounts:login')
        else:
            messages.error(request, 'Please select Customer or Seller.')

    return render(request, 'accounts/register.html')


# ── LOGOUT (POST only to prevent CSRF logout attacks) ─────────
def logout_view(request):
    if request.method == 'POST':
        request.session.flush()
        messages.success(request, 'Logged out successfully.')
        return redirect('accounts:login')
    # GET logout — still works for backward compat with existing links
    request.session.flush()
    return redirect('accounts:login')


# ── CUSTOMER DASHBOARD ────────────────────────────────────────
def customer_dashboard(request):
    if request.session.get('user_role') != 'customer':
        return redirect('accounts:login')

    from products.models import Wishlist, Review
    from orders.models import Order
    from django.db.models import Sum

    customer         = Customer.objects.get(id=request.session['user_id'])
    cart             = request.session.get('cart', {})
    recent_orders    = Order.objects.filter(customer=customer).prefetch_related('items').order_by('-created_at')[:5]
    total_orders     = Order.objects.filter(customer=customer).count()
    pending_orders   = Order.objects.filter(customer=customer, status='pending').count()
    delivered_orders = Order.objects.filter(customer=customer, status='delivered').count()
    total_spent      = Order.objects.filter(customer=customer).exclude(status='cancelled').aggregate(t=Sum('total'))['t'] or 0
    wishlist_count   = Wishlist.objects.filter(customer=customer).count()
    reviews_count    = Review.objects.filter(customer=customer).count()

    # Cart total quantity (not just unique item count)
    cart_total_qty = sum(cart.values())

    return render(request, 'accounts/customer_dashboard.html', {
        'name':             customer.name,
        'customer':         customer,
        'recent_orders':    recent_orders,
        'total_orders':     total_orders,
        'pending_orders':   pending_orders,
        'delivered_orders': delivered_orders,
        'total_spent':      total_spent,
        'wishlist_count':   wishlist_count,
        'reviews_count':    reviews_count,
        'cart_count':       cart_total_qty,
    })


# ── SELLER DASHBOARD (simple redirect) ────────────────────────
def seller_dashboard(request):
    if request.session.get('user_role') != 'seller':
        return redirect('accounts:login')
    return redirect('/seller/dashboard/')


# ── ADMIN DASHBOARD ───────────────────────────────────────────
def admin_dashboard(request):
    if request.session.get('user_role') != 'admin':
        return redirect('accounts:login')

    from products.models import Product, Category
    from orders.models import Order
    from django.db.models import Sum

    total_revenue = Order.objects.exclude(status='cancelled').aggregate(t=Sum('total'))['t'] or 0

    return render(request, 'accounts/admin_dashboard.html', {
        'name':             request.session.get('user_name'),
        'total_customers':  Customer.objects.count(),
        'total_sellers':    Seller.objects.count(),
        'total_products':   Product.objects.count(),
        'total_orders':     Order.objects.count(),
        'total_categories': Category.objects.count(),
        'pending_sellers':  Seller.objects.filter(is_approved=False).count(),
        'total_revenue':    total_revenue,
        'all_sellers':      Seller.objects.all().order_by('-id'),
        'all_customers':    Customer.objects.all().order_by('-id'),
    })


# ── CUSTOMER PROFILE EDIT ─────────────────────────────────────
def customer_profile(request):
    if request.session.get('user_role') != 'customer':
        return redirect('accounts:login')
    try:
        customer = Customer.objects.get(id=request.session['user_id'])
    except Customer.DoesNotExist:
        return redirect('accounts:login')

    if request.method == 'POST':
        action = request.POST.get('action', 'profile')
        if action == 'profile':
            name  = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            if not name:
                messages.error(request, 'Name cannot be empty.')
            else:
                customer.name  = name
                customer.phone = phone
                customer.save(update_fields=['name', 'phone'])
                request.session['user_name'] = name
                request.session.modified = True
                messages.success(request, 'Profile updated successfully!')
            return redirect('/accounts/profile/')
        elif action == 'password':
            current = request.POST.get('current_password', '')
            new_pw  = request.POST.get('new_password', '')
            confirm = request.POST.get('confirm_password', '')
            if not check_password(current, customer.password):
                messages.error(request, 'Current password is incorrect.')
            elif new_pw != confirm:
                messages.error(request, 'New passwords do not match.')
            else:
                valid, err = _validate_password_strength(new_pw)
                if not valid:
                    messages.error(request, err)
                else:
                    customer.password = make_password(new_pw)
                    customer.save(update_fields=['password'])
                    messages.success(request, 'Password changed successfully!')
            return redirect('/accounts/profile/')

    return render(request, 'accounts/profile.html', {'customer': customer})


# ── SELLER PROFILE EDIT ───────────────────────────────────────
def seller_profile(request):
    if request.session.get('user_role') != 'seller':
        return redirect('accounts:login')
    try:
        seller = Seller.objects.get(id=request.session['user_id'])
    except Seller.DoesNotExist:
        return redirect('accounts:login')

    if request.method == 'POST':
        action = request.POST.get('action', 'profile')
        if action == 'profile':
            name  = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            if not name:
                messages.error(request, 'Name cannot be empty.')
            else:
                seller.name  = name
                seller.phone = phone
                seller.save(update_fields=['name', 'phone'])
                request.session['user_name'] = name
                request.session.modified = True
                messages.success(request, 'Profile updated!')
            return redirect('/accounts/seller-profile/')
        elif action == 'password':
            current = request.POST.get('current_password', '')
            new_pw  = request.POST.get('new_password', '')
            confirm = request.POST.get('confirm_password', '')
            if not check_password(current, seller.password):
                messages.error(request, 'Current password is incorrect.')
            elif new_pw != confirm:
                messages.error(request, 'New passwords do not match.')
            else:
                valid, err = _validate_password_strength(new_pw)
                if not valid:
                    messages.error(request, err)
                else:
                    seller.password = make_password(new_pw)
                    seller.save(update_fields=['password'])
                    messages.success(request, 'Password changed!')
            return redirect('/accounts/seller-profile/')

    return render(request, 'accounts/seller_profile.html', {'seller': seller})


# ── FACE RECOGNITION VIEWS ────────────────────────────────────

@csrf_exempt
def face_register(request):
    """Save face descriptor for logged-in customer."""
    if request.session.get('user_role') != 'customer':
        return JsonResponse({'success': False, 'error': 'Login required'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST only'}, status=405)
    try:
        data       = _json.loads(request.body)
        descriptor = data.get('descriptor')
        if not descriptor or len(descriptor) != 128:
            return JsonResponse({'success': False, 'error': 'Invalid face data'})
        customer = Customer.objects.get(id=request.session['user_id'])
        customer.face_descriptor = _json.dumps(descriptor)
        customer.save(update_fields=['face_descriptor'])
        return JsonResponse({'success': True, 'message': 'Face registered successfully!'})
    except Customer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Customer not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
def face_login(request):
    """Match incoming descriptor against all customers, log in on match."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST only'}, status=405)
    try:
        data       = _json.loads(request.body)
        descriptor = data.get('descriptor')
        if not descriptor or len(descriptor) != 128:
            return JsonResponse({'success': False, 'error': 'Invalid face data'})

        import math

        def euclidean(a, b):
            return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

        THRESHOLD  = 0.50
        best_match = None
        best_dist  = float('inf')

        customers = Customer.objects.exclude(face_descriptor__isnull=True).exclude(face_descriptor='')
        for customer in customers:
            try:
                stored = _json.loads(customer.face_descriptor)
                dist   = euclidean(descriptor, stored)
                if dist < best_dist:
                    best_dist  = dist
                    best_match = customer
            except Exception:
                continue

        if best_match and best_dist < THRESHOLD:
            request.session['user_id']   = best_match.id
            request.session['user_role'] = 'customer'
            request.session['user_name'] = best_match.name
            request.session.modified = True
            return JsonResponse({
                'success':  True,
                'name':     best_match.name,
                'redirect': '/',
                'distance': round(best_dist, 4),
            })
        else:
            return JsonResponse({'success': False,
                'error': 'Face not recognised. Please login with email/password.'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
