from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import F
from .models import DiscountCode
from accounts.models import Seller


def seller_required(request):
    if request.session.get('user_role') != 'seller':
        return False
    try:
        seller = Seller.objects.get(id=request.session['user_id'])
        return seller.is_approved
    except Seller.DoesNotExist:
        return False


def discount_list(request):
    if not seller_required(request):
        messages.error(request, 'Please login as a seller.')
        return redirect('/accounts/login/')

    seller = Seller.objects.get(id=request.session['user_id'])
    codes  = DiscountCode.objects.filter(created_by=seller).order_by('-created_at')

    return render(request, 'seller/discounts.html', {
        'codes':  codes,
        'seller': seller,
    })


def add_discount(request):
    if not seller_required(request):
        return redirect('/accounts/login/')

    if request.method == 'POST':
        code                = request.POST.get('code', '').strip().upper()
        discount_type       = request.POST.get('discount_type')
        discount_value      = request.POST.get('discount_value')
        minimum_order_value = request.POST.get('minimum_order_value', 0)
        expiry_date         = request.POST.get('expiry_date')
        usage_limit         = request.POST.get('usage_limit', 1)

        if DiscountCode.objects.filter(code=code).exists():
            messages.error(request, f'Code "{code}" already exists.')
            return redirect('/seller/discounts/')

        seller = Seller.objects.get(id=request.session['user_id'])
        DiscountCode.objects.create(
            code=code,
            discount_type=discount_type,
            discount_value=discount_value,
            minimum_order_value=minimum_order_value,
            expiry_date=expiry_date,
            usage_limit=usage_limit,
            created_by=seller,
        )
        messages.success(request, f'Discount code "{code}" created!')
        return redirect('/seller/discounts/')

    return redirect('/seller/discounts/')


def delete_discount(request, code_id):
    if not seller_required(request):
        return redirect('/accounts/login/')
    if request.method != 'POST':
        return redirect('/seller/discounts/')

    seller = Seller.objects.get(id=request.session['user_id'])
    try:
        code = DiscountCode.objects.get(id=code_id, created_by=seller)
        code.delete()
        messages.success(request, 'Discount code deleted.')
    except DiscountCode.DoesNotExist:
        messages.error(request, 'Code not found.')
    return redirect('/seller/discounts/')


def toggle_discount(request, code_id):
    if not seller_required(request):
        return redirect('/accounts/login/')
    if request.method != 'POST':
        return redirect('/seller/discounts/')

    seller = Seller.objects.get(id=request.session['user_id'])
    try:
        code           = DiscountCode.objects.get(id=code_id, created_by=seller)
        code.is_active = not code.is_active
        code.save()
        status = 'activated' if code.is_active else 'deactivated'
        messages.success(request, f'Code "{code.code}" {status}.')
    except DiscountCode.DoesNotExist:
        messages.error(request, 'Code not found.')
    return redirect('/seller/discounts/')


def apply_discount(request):
    if request.method == 'POST':
        code_str = request.POST.get('discount_code', '').strip().upper()
        cart     = request.session.get('cart', {})

        cart_total = 0
        from products.models import Product
        for pid, qty in cart.items():
            try:
                p = Product.objects.get(id=int(pid))
                cart_total += float(p.price) * qty
            except Product.DoesNotExist:
                pass

        try:
            code  = DiscountCode.objects.get(code=code_str)
            valid, msg = code.is_valid(cart_total)
            if valid:
                discount_amount = float(code.get_discount_amount(cart_total))
                request.session['discount_code']   = code_str
                request.session['discount_amount'] = discount_amount
                request.session.modified = True
                messages.success(request, f'Code "{code_str}" applied! You save ₹{discount_amount:.2f}')
            else:
                messages.error(request, msg)
                request.session['discount_code']   = ''
                request.session['discount_amount'] = 0
        except DiscountCode.DoesNotExist:
            messages.error(request, 'Invalid discount code.')
            request.session['discount_code']   = ''
            request.session['discount_amount'] = 0

    return redirect('/cart/')


def remove_discount(request):
    request.session['discount_code']   = ''
    request.session['discount_amount'] = 0
    request.session.modified = True
    messages.success(request, 'Discount removed.')
    return redirect('/cart/')
